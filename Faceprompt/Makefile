PYTHON ?= python3
PYTHONPATH=src
SCENE ?= morning-window-softlight
HAIRSTYLE ?= male-preset-male-american-forward-spike
GENDER ?= male

.PHONY: summary lint test render-example interactive interactive-blocks list-scenes list-hairstyles render-prompt render-hairstyle render-scene

summary:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli summary

lint:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli validate

test:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m unittest discover -s tests

render-example:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli render --scene indoor-film-lifestyle --hairstyle female-french-lazy-waves

list-scenes:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli list --category scene

list-hairstyles:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli list --category hairstyle --gender $(GENDER)

render-prompt:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli render --scene $(SCENE) --hairstyle $(HAIRSTYLE)

render-hairstyle:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli render-hairstyle-only --hairstyle $(HAIRSTYLE)

render-scene:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli render-scene-only --scene $(SCENE)

interactive:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli interactive

interactive-blocks:
	PYTHONPATH=$(PYTHONPATH) $(PYTHON) -m faceprompt.cli interactive-blocks
