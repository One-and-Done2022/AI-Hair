PYTHON ?= python3
PYTHONPATH=src

.PHONY: summary lint test render-example interactive

summary:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli summary

lint:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli validate

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests

render-example:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli render --scene indoor-film-lifestyle --hairstyle female-french-lazy-waves

interactive:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli interactive
