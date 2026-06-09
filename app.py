import csv
import os
from datetime import datetime

import questionary
from rich.console import Console
from rich.progress import track
from rich.table import Table

from core import (
    KeywordSpec,
    collect_cv_files,
    extract_keywords_from_jd,
    extract_text_from_pdf,
    match_cv_with_keywords,
    normalize_text,
)

console = Console()

MUST_HAVE_WEIGHT = 3


class ATSCliApp:
    def __init__(self):
        self.jd_path = ""
        self.cv_folder = ""
        self.keywords: list[KeywordSpec] = []
        self.results: list[dict] = []
        self.min_score = 0.0
        self.failed_files: list[str] = []
        self.scanned_files: list[str] = []

    def get_inputs(self):
        console.print("[bold cyan]==================================================[/bold cyan]")
        console.print("[bold cyan]   ATS LOCAL TOOL - HYBRID RULE-BASED - KHÔNG AI   [/bold cyan]")
        console.print("[bold cyan]==================================================[/bold cyan]\n")

        self.jd_path = questionary.path(
            "👉 Kéo thả hoặc nhập đường dẫn file JD (.pdf):"
        ).ask()

        self.cv_folder = questionary.path(
            "👉 Kéo thả hoặc nhập đường dẫn THƯ MỤC chứa các file CV (.pdf):"
        ).ask()

        min_score_str = questionary.text(
            "Ngưỡng điểm tối thiểu để hiển thị (0-100, mặc định 0):",
            default="0",
        ).ask()
        try:
            self.min_score = max(0.0, min(100.0, float(min_score_str or "0")))
        except ValueError:
            self.min_score = 0.0

    def clean_path(self, path_str: str) -> str:
        if path_str:
            return path_str.strip("'\" ")
        return ""

    def _review_keywords(self) -> bool:
        console.print("\n[bold yellow]Từ khóa tự động trích từ JD:[/bold yellow]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("#", justify="center", width=4)
        table.add_column("Từ khóa", style="cyan")
        table.add_column("Trọng số", justify="center")
        table.add_column("Loại", style="dim")
        table.add_column("Nguồn", style="dim")

        for idx, kw in enumerate(self.keywords, start=1):
            label = "Bắt buộc" if kw.weight >= MUST_HAVE_WEIGHT else "Ưu tiên"
            table.add_row(str(idx), kw.term, str(kw.weight), label, kw.source)
        console.print(table)

        action = questionary.select(
            "Bạn muốn tiếp tục với từ khóa này?",
            choices=[
                "Tiếp tục chấm CV",
                "Thêm từ khóa thủ công",
                "Xóa từ khóa",
                "Hủy",
            ],
        ).ask()

        if action == "Hủy":
            return False
        if action == "Thêm từ khóa thủ công":
            self._add_manual_keywords()
            return self._review_keywords()
        if action == "Xóa từ khóa":
            self._remove_keywords()
            return self._review_keywords()
        return True

    def _add_manual_keywords(self):
        term = questionary.text("Nhập từ khóa mới:").ask()
        if not term or not term.strip():
            return
        weight_str = questionary.select(
            "Mức độ quan trọng:",
            choices=["Bắt buộc (3)", "Quan trọng (2)", "Ưu tiên (1)"],
        ).ask()
        weight_map = {"Bắt buộc (3)": 3, "Quan trọng (2)": 2, "Ưu tiên (1)": 1}
        self.keywords.append(
            KeywordSpec(
                term=term.strip(),
                weight=weight_map.get(weight_str, 1),
                source="manual",
            )
        )

    def _remove_keywords(self):
        if not self.keywords:
            return
        choices = [f"{kw.term} (w={kw.weight})" for kw in self.keywords]
        selected = questionary.checkbox("Chọn từ khóa cần xóa:", choices=choices).ask()
        if not selected:
            return
        remove_terms = {s.split(" (w=")[0] for s in selected}
        self.keywords = [kw for kw in self.keywords if kw.term not in remove_terms]

    def process_ats(self):
        self.jd_path = self.clean_path(self.jd_path)
        self.cv_folder = self.clean_path(self.cv_folder)

        if not self.jd_path or not os.path.exists(self.jd_path):
            console.print("[bold red]❌ Lỗi: Đường dẫn file JD không hợp lệ![/bold red]")
            return

        if not self.cv_folder or not os.path.exists(self.cv_folder):
            console.print("[bold red]❌ Lỗi: Đường dẫn thư mục CV không hợp lệ![/bold red]")
            return

        console.print("\n[yellow]⏳ Đang phân tích JD (section-aware + skill dictionary)...[/yellow]")
        jd_result = extract_text_from_pdf(self.jd_path)
        if jd_result.error:
            console.print(f"[bold red]❌ Lỗi đọc JD: {jd_result.error}[/bold red]")
            return
        if jd_result.likely_scanned or len(normalize_text(jd_result.text)) < 50:
            console.print("[bold red]❌ Lỗi: JD có thể là file scan — không trích được text.[/bold red]")
            return

        self.keywords = extract_keywords_from_jd(jd_result.text)
        if not self.keywords:
            console.print("[bold red]❌ Lỗi: Không trích được từ khóa từ JD.[/bold red]")
            return

        if not self._review_keywords():
            console.print("[yellow]Đã hủy.[/yellow]")
            return

        files = collect_cv_files(self.cv_folder, recursive=True)
        if not files:
            console.print("[bold yellow]⚠ Không tìm thấy file PDF CV nào.[/bold yellow]")
            return

        console.print(f"\n[cyan]Tìm thấy {len(files)} file CV. Đang chấm điểm...[/cyan]\n")

        for full_path in track(files, description="⚡ Đang xếp hạng CV..."):
            file_name = os.path.basename(full_path)
            cv_result = extract_text_from_pdf(full_path)

            if cv_result.error:
                self.failed_files.append(file_name)
                continue

            warning = None
            if cv_result.likely_scanned:
                self.scanned_files.append(file_name)
                warning = "PDF có thể scan — cần kiểm tra thủ công"

            match = match_cv_with_keywords(cv_result.text, self.keywords)
            if match.warning:
                warning = match.warning

            if match.score < self.min_score:
                continue

            self.results.append({
                "file_name": file_name,
                "score": match.score,
                "matched_count": f"{len(match.matched)}/{len(self.keywords)}",
                "must_have": f"{match.must_have_matched}/{match.must_have_total}",
                "nice_have": f"{match.nice_have_matched}/{match.nice_have_total}",
                "matched_keywords": ", ".join(match.matched) if match.matched else "Không trùng",
                "warning": warning or "",
            })

        self.results.sort(key=lambda x: x["score"], reverse=True)

    def display_results(self):
        if self.failed_files:
            console.print(
                f"[bold red]❌ Không đọc được {len(self.failed_files)} file: "
                f"{', '.join(self.failed_files)}[/bold red]"
            )
        if self.scanned_files:
            console.print(
                f"[bold yellow]⚠ Cảnh báo scan {len(self.scanned_files)} file: "
                f"{', '.join(self.scanned_files)}[/bold yellow]"
            )

        if not self.results:
            console.print("[bold yellow]⚠ Không có kết quả phù hợp ngưỡng lọc.[/bold yellow]")
            return

        table = Table(
            title="\n[bold green]📊 KẾT QUẢ XẾP HẠNG CV ỨNG VIÊN[/bold green]",
            title_justify="center",
        )
        table.add_column("Hạng", justify="center", style="cyan", no_wrap=True)
        table.add_column("Tên file CV", style="magenta", max_width=35)
        table.add_column("Điểm", justify="right")
        table.add_column("Bắt buộc", justify="center", style="yellow")
        table.add_column("Ưu tiên", justify="center")
        table.add_column("Từ khóa khớp", style="white", max_width=40)
        table.add_column("Cảnh báo", style="dim red", max_width=25)

        for idx, res in enumerate(self.results, start=1):
            score = res["score"]
            if score >= 70:
                match_style = "bold green"
            elif score >= 40:
                match_style = "bold yellow"
            elif score > 0:
                match_style = "white"
            else:
                match_style = "dim red"

            table.add_row(
                str(idx),
                res["file_name"],
                f"[{match_style}]{score}%[/{match_style}]",
                res["must_have"],
                res["nice_have"],
                res["matched_keywords"],
                res["warning"],
            )

        console.print(table)
        self._offer_export()

    def _offer_export(self):
        export = questionary.confirm("Xuất kết quả ra file CSV?", default=True).ask()
        if not export:
            console.print("\n[bold green]🎉 Hoàn thành![/bold green]")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(self.cv_folder, f"ats_results_{timestamp}.csv")
        fieldnames = [
            "file_name", "score", "must_have", "nice_have",
            "matched_count", "matched_keywords", "warning",
        ]
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)

        console.print(f"\n[bold green]✅ Đã xuất CSV: {out_path}[/bold green]")

    def run(self):
        self.get_inputs()
        self.process_ats()
        self.display_results()


if __name__ == "__main__":
    app = ATSCliApp()
    app.run()
