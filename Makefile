# Plant flashcards - build helper.
# One deck = one folder with plants.csv + images/ (see README.md).

DECKS := $(sort $(dir $(wildcard */plants.csv)))

.PHONY: help build lint clean clean_all

help:  ## list targets and decks
	@echo "targets: build, lint, clean, clean_all"
	@echo "decks: $(if $(DECKS),$(DECKS),none found)"

build:  ## build every deck (plants.csv -> <deck>.pdf)
	./make_flashcards.py --all

lint:  ## ruff + mypy (the same gates the CI pipeline runs)
	ruff check .
	mypy make_flashcards.py find_photo.py

clean:  ## remove caches and generated artifacts (keeps the PDFs)
	rm -rf .mypy_cache .ruff_cache __pycache__ */__pycache__
	rm -f dbg*.png
	./make_flashcards.py --all --clean

clean_all:  ## also remove the built PDFs
	rm -rf .mypy_cache .ruff_cache __pycache__ */__pycache__
	rm -f dbg*.png
	./make_flashcards.py --all --clean-all
