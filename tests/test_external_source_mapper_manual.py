from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.beckett_parser import parse_beckett_checklist
from parsers.tcdb_parser import parse_tcdb_checklist
from exporter.external_source_mapper import build_checklist_rows
from exporter.final_export import write_final_csv, sort_rows_by_brand

BECKETT_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "beckett_2025_bowman_baseball.html"
TCDB_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "tcdb_1972_topps_sample.html"


def run():
    failures = []

    def check(label, cond):
        if not cond:
            failures.append(label)

    # --- Beckett end-to-end ---
    beckett_html = BECKETT_FIXTURE.read_text(encoding="utf-8")
    beckett_rows = parse_beckett_checklist(beckett_html)
    beckett_context = {"product": "2025 Bowman", "sport": "Baseball"}
    beckett_checklist_rows = build_checklist_rows(beckett_rows, beckett_context)

    check("beckett rows produced", len(beckett_checklist_rows) == len(beckett_rows))
    sample = next(r for r in beckett_checklist_rows if r.card_number == "1")
    check("beckett year parsed", sample.year == "2025")
    check("beckett brand parsed", sample.brand == "Bowman")
    check("beckett set blank", sample.set == "")
    check("beckett sub_type is sport", sample.sub_type == "Baseball")
    check("beckett type is Sports", sample.type == "Sports")
    check("beckett player carried through", sample.player == "Mike Trout")

    out_path = "/tmp/beckett_test_output.csv"
    sorted_rows = sort_rows_by_brand(beckett_checklist_rows)
    write_final_csv(sorted_rows, out_path)
    csv_text = Path(out_path).read_text(encoding="utf-8")
    check("beckett CSV has header", csv_text.startswith("type,sport,year,brand,set,insert,attributes,card_number,player,team,base,base_serial,parallel_1,serial_1"))
    check("beckett CSV has Mike Trout row", "Mike Trout" in csv_text)

    # --- TCDB end-to-end ---
    tcdb_html = TCDB_FIXTURE.read_text(encoding="utf-8")
    tcdb_rows = parse_tcdb_checklist(tcdb_html)
    tcdb_context = {"product": "1972 Topps", "sport": "Baseball"}
    tcdb_checklist_rows = build_checklist_rows(tcdb_rows, tcdb_context)

    check("tcdb rows produced", len(tcdb_checklist_rows) == len(tcdb_rows))
    sample18 = next(r for r in tcdb_checklist_rows if r.card_number == "18")
    check("tcdb year parsed", sample18.year == "1972")
    check("tcdb brand parsed", sample18.brand == "Topps")
    check("tcdb parallels carried through (2 VAR slots)", len(sample18.parallels) == 2)

    out_path2 = "/tmp/tcdb_test_output.csv"
    sorted_rows2 = sort_rows_by_brand(tcdb_checklist_rows)
    write_final_csv(sorted_rows2, out_path2)
    csv_text2 = Path(out_path2).read_text(encoding="utf-8")
    check("tcdb CSV has 2 parallel column pairs (widened for card 18)", "parallel_2,serial_2" in csv_text2)
    check("tcdb CSV has Juan Pizarro row", "Juan Pizarro" in csv_text2)

    print("Beckett CSV sample:")
    print(csv_text[:500])
    print()
    print("TCDB CSV sample:")
    print(csv_text2[:600])

    print()
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    else:
        print("All end-to-end checks passed.")


if __name__ == "__main__":
    run()
