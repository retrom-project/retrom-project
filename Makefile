SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
RETROM_DIR ?= $(if $(PFB),$(abspath .worktree/$(PFB)/project/retrom),$(abspath project/retrom))
RUNTIME_DIR ?= $(abspath $(RETROM_DIR)/../retrom-runtime)
RETROM_NODE_HOME ?= $(RETROM_DIR)/.cache/tools/node-v24.18.0-linux-x64
WORKSPACE_ARGS = --retrom-dir "$(RETROM_DIR)" $(if $(PFB),--pfb "$(PFB)") $(if $(REPOS),--repos $(REPOS))

PFB_TARGETS := pfb-init pfb-validate pfb-build pfb-up pfb-use pfb-restart \
	pfb-down pfb-status pfb-logs pfb-verify pfb-destroy pfb-core-build \
	pfb-provider-import pfb-migrate-storage pfb-data-reset \
	pfb-gateway-up pfb-gateway-down

.PHONY: help validate init check update status install-deps dev pfb-list pfb-remove $(PFB_TARGETS)

help:
	@echo 'Retrom development workspace'
	@echo
	@echo '  make init          clone Retrom, then its branch-owned dependency catalog'
	@echo '  make init PFB=name [REPOS="id ..."]  prepare isolated source worktrees'
	@echo '  make check         validate existing checkouts and origins'
	@echo '  make update        switch clean checkouts to manifest defaults and update them'
	@echo '  make status        show child branch, commit and dirty state'
	@echo '  make install-deps  install Retrom and retrom-runtime dependencies'
	@echo '  make dev           run Retrom development services on localhost:4000'
	@echo '  make pfb-list      show all PFB development flows in this workspace'
	@echo '  make pfb-remove    destroy one PFB and remove all of its clean worktrees'
	@echo '  make pfb-<action>  pass a PFB action through to Retrom'

validate:
	@$(PYTHON) scripts/workspace.py validate $(WORKSPACE_ARGS)

init:
	@$(PYTHON) scripts/workspace.py init $(WORKSPACE_ARGS)

check:
	@$(PYTHON) scripts/workspace.py check $(WORKSPACE_ARGS)

update:
	@$(PYTHON) scripts/workspace.py update $(WORKSPACE_ARGS)

status:
	@$(PYTHON) scripts/workspace.py status $(WORKSPACE_ARGS)

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
