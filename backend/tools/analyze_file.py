"""Анализ одного видео без API — для отладки правил и подбора порогов.

    python -m tools.analyze_file video.mov --out out/video_017

Сохраняет result.json (как в API), кадры-доказательства *.jpg, timeline.csv
(покадровое состояние сцены) и zones.json (найденные зоны — можно поправить и
передать обратно через --zones или ZONES_FILE).
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
from pathlib import Path

from .common import add_analyzer_arguments, build_analyzer


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    add_analyzer_arguments(parser)
    args = parser.parse_args()

    out = args.out or Path("out") / args.video.stem
    out.mkdir(parents=True, exist_ok=True)
    analyzer = build_analyzer(args)

    def progress(fraction: float, stage: str) -> None:
        print(f"\r{fraction:6.1%}  {stage:<40}", end="", flush=True)

    result = analyzer.analyze(args.video, progress=progress, debug=True)
    print()

    debug = result.pop("debug")
    with (out / "timeline.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(debug["timeline"][0]))
        writer.writeheader()
        writer.writerows(debug["timeline"])

    for number, violation in enumerate(result["violations"], start=1):
        for k, frame in enumerate(violation["evidence_frames"], start=1):
            name = f"{number:02d}_{violation['code']}_{frame['timestamp_sec']:.2f}s_{k}.jpg"
            (out / name).write_bytes(base64.b64decode(frame["image_base64"]))

    layout = result["analysis"]["layout"]
    if layout:
        (out / "zones.json").write_text(json.dumps(
            {key: layout[key] for key in ("cashier_side", "workplace", "client_counter", "desk") if layout[key]},
            ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Вердикт: {result['verdict']}  ({result['analysis']['elapsed_sec']} с, "
          f"{result['video']['frames_analyzed']} кадров)")
    for violation in result["violations"]:
        print(f"  {violation['timecode_sec']:7.2f} с  [{violation['confidence']:.2f}] {violation['type']}")
    for rejected in debug["rejected_events"]:
        print(f"  (ниже порога) {rejected['timecode_sec']:7.2f} с  [{rejected['confidence']:.2f}] {rejected['code']}")
    print(f"Файлы: {out.resolve()}")


if __name__ == "__main__":
    main()
