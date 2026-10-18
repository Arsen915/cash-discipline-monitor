"""Оценка качества на размеченном датасете (критерии 1–2 ТЗ: вердикт и таймкод).

    python -m tools.evaluate --videos dataset/ --labels labels.csv --out eval/

labels.csv (UTF-8, с заголовком). Одна строка на событие; для видео без нарушения —
одна строка с пустым таймкодом:

    file,label,timecode_sec
    video_001.mov,violation,11
    video_001.mov,violation,47.5
    video_002.mov,no_violation,

label: violation / нарушение / 1 — нарушение, всё остальное — нет нарушения.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from .common import add_analyzer_arguments, build_analyzer

POSITIVE = {"violation", "нарушение", "1", "true", "yes", "да"}


def load_labels(path: Path) -> dict[str, dict]:
    labels: dict[str, dict] = defaultdict(lambda: {"violation": False, "timecodes": []})
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = row["file"].strip()
            entry = labels[name]
            if row.get("label", "").strip().lower() in POSITIVE:
                entry["violation"] = True
                value = (row.get("timecode_sec") or "").strip().replace(",", ".")
                if value:
                    entry["timecodes"].append(float(value))
    return dict(labels)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("eval"))
    parser.add_argument("--tolerance", type=float, default=2.0, help="Допуск по таймкоду, с")
    add_analyzer_arguments(parser)
    args = parser.parse_args()

    labels = load_labels(args.labels)
    analyzer = build_analyzer(args)
    args.out.mkdir(parents=True, exist_ok=True)

    rows, tp, fp, tn, fn = [], 0, 0, 0, 0
    timecode_errors, timecode_hits, labelled_events = [], 0, 0
    for name, truth in sorted(labels.items()):
        path = args.videos / name
        if not path.is_file():
            print(f"[skip] нет файла {path}")
            continue
        started = time.monotonic()
        try:
            result = analyzer.analyze(path)
        except Exception as exc:  # фиксируем и идём дальше: оценка не должна обрываться
            print(f"[fail] {name}: {exc}")
            rows.append({"file": name, "truth": truth["violation"], "predicted": None, "error": str(exc)})
            continue
        elapsed = time.monotonic() - started
        predicted = result["verdict"] == "violation"
        tp += predicted and truth["violation"]
        fp += predicted and not truth["violation"]
        tn += not predicted and not truth["violation"]
        fn += not predicted and truth["violation"]

        predicted_times = [v["timecode_sec"] for v in result["violations"]]
        errors = []
        for labelled in truth["timecodes"]:
            labelled_events += 1
            if predicted_times:
                error = min(abs(t - labelled) for t in predicted_times)
                errors.append(error)
                timecode_errors.append(error)
                timecode_hits += error <= args.tolerance
        mark = "OK " if predicted == truth["violation"] else "ERR"
        print(f"[{mark}] {name}: истина={'V' if truth['violation'] else '-'} "
              f"прогноз={'V' if predicted else '-'} t={predicted_times} метки={truth['timecodes']} "
              f"({elapsed:.1f} с)")
        rows.append({
            "file": name,
            "truth": truth["violation"],
            "predicted": predicted,
            "labelled_timecodes": truth["timecodes"],
            "violations": [{k: v[k] for k in ("code", "timecode_sec", "confidence")} for v in result["violations"]],
            "timecode_errors": errors,
            "elapsed_sec": round(elapsed, 2),
        })

    total = tp + fp + tn + fn
    summary = {
        "videos": total,
        "accuracy": round((tp + tn) / total, 4) if total else None,
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "timecode_hit_rate": round(timecode_hits / labelled_events, 4) if labelled_events else None,
        "timecode_median_error_sec": (round(sorted(timecode_errors)[len(timecode_errors) // 2], 2)
                                      if timecode_errors else None),
        "tolerance_sec": args.tolerance,
    }
    (args.out / "report.json").write_text(json.dumps({"summary": summary, "videos": rows},
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
