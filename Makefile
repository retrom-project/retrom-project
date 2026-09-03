SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
RETROM_DIR ?= $(abspath project/retrom)
RUNTIME_DIR ?= $(abspath project/retrom-runtime)
RETROM_NODE_HOME ?= $(RETROM_DIR)/.cache/tools/node-v24.18.0-linux-x64

PFB_TARGETS := pfb-init pfb-validate pfb-build pfb-up pfb-use pfb-restart \
	pfb-down pfb-status pfb-logs pfb-verify pfb-prune pfb-destroy \
	pfb-migrate-storage pfb-data-reset \
	pfb-gateway-up pfb-gateway-down

.PHONY: help validate init check update status install-deps dev pfb-list pfb-remove $(PFB_TARGETS)

help:
	@echo 'Retrom development workspace'
	@echo
	@echo '  make init          clone missing repositories from manifest.yaml'
	@echo '  make check         validate existing checkouts and origins'
	@echo '  make update        switch clean checkouts to manifest defaults and update them'
	@echo '  make status        show child branch, commit and dirty state'
	@echo '  make install-deps  install Retrom and retrom-runtime dependencies'
	@echo '  make dev           run Retrom development services on localhost:4000'
	@echo '  make pfb-list      show all PFB development flows in this workspace'
	@echo '  make pfb-remove    destroy one PFB and remove all of its clean worktrees'
	@echo '  make pfb-<action>  pass a PFB action through to Retrom'

validate:
	@$(PYTHON) scripts/workspace.py validate

init: validate
	@$(PYTHON) scripts/workspace.py init

check: validate
	@$(PYTHON) scripts/workspace.py check

update: validate
	@$(PYTHON) scripts/workspace.py update

status: validate
	@$(PYTHON) scripts/workspace.py status

install-deps: init
	@$(MAKE) -C "$(RETROM_DIR)" install-deps
	@cd "$(RUNTIME_DIR)" && PATH="$(RETROM_NODE_HOME)/bin:$$PATH" npm ci

dev:
	@$(MAKE) -C "$(RETROM_DIR)" dev

pfb-list:
	@$(PYTHON) scripts/pfb_list.py

pfb-remove:
	@$(PYTHON) scripts/pfb_remove.py --pfb "$(PFB)"

$(PFB_TARGETS):
	@$(MAKE) -C "$(RETROM_DIR)" $@
