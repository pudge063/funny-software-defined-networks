# Тесты топологий lab4: unit-тесты на фикстурах + Mininet/Floodlight.
# Mininet установлен в системный python3, поэтому venv видит system site-packages.

PYTHON        ?= /usr/bin/python3
VENV          ?= .venv
VENV_PY       := $(VENV)/bin/python
FLOODLIGHT_JAR ?= $(HOME)/floodlight/target/floodlight.jar
PYTEST_ARGS   ?=
OPENFLOW      ?= OpenFlow13

.PHONY: venv test test-unit test-integration clean

$(VENV_PY):
	$(PYTHON) -m venv --without-pip --system-site-packages $(VENV)
	$(VENV_PY) -m pip install --quiet 'pytest>=8' 'pytest-timeout>=2.3'

venv: $(VENV_PY)

test: venv
	sudo env "PATH=$(PATH)" FLOODLIGHT_JAR=$(FLOODLIGHT_JAR) OPENFLOW=$(OPENFLOW) $(VENV_PY) -m pytest $(PYTEST_ARGS)

test-unit: venv
	$(VENV_PY) -m pytest -m "not integration" $(PYTEST_ARGS)

test-integration: venv
	sudo env "PATH=$(PATH)" FLOODLIGHT_JAR=$(FLOODLIGHT_JAR) OPENFLOW=$(OPENFLOW) $(VENV_PY) -m pytest -m integration $(PYTEST_ARGS)

clean:
	sudo mn -c
	rm -rf $(VENV) .pytest_cache
