"""Общие функции для CLI-утилит: сборка анализатора из аргументов командной строки."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.pipeline.analyzer import VideoAnalyzer
from app.pipeline.detector import create_detector
from app.pipeline.rule_config import load_rule_config

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def add_analyzer_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model", type=Path,
                        default=Path(os.environ.get("MODEL_PATH", BACKEND_ROOT / "models" / "yolox_tiny.onnx")))
    parser.add_argument("--backend", default=os.environ.get("DETECTOR_BACKEND", "yolox"))
    parser.add_argument("--zones", type=Path, default=None, help="JSON с зонами кассы (иначе автокалибровка)")
    parser.add_argument("--rules", type=Path, default=None, help="JSON с переопределением порогов правил")
    parser.add_argument("--fps", type=float, default=3.0, help="Частота анализа кадров")
    parser.add_argument("--no-zoom", action="store_true", help="Отключить дозум на кассира")


def build_analyzer(args: argparse.Namespace) -> VideoAnalyzer:
    config = load_rule_config(args.rules)
    detector = create_detector(args.backend, args.model, config.detector_labels, config.detector_min_conf)
    return VideoAnalyzer(detector, config, analysis_fps=args.fps, zones_file=args.zones,
                         object_zoom=not args.no_zoom, budget_sec=10_000)
