"""Allow running: python -m lip.c4_dispute_classifier.corpus.cfpb_label_mapper"""
import sys

from .cfpb_label_mapper import main

sys.exit(main() or 0)
