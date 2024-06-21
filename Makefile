.PHONY : env update-lock install init update
.DEFAULT_GOAL := init

env :
	poetry env use 3.12

update-lock :
	poetry lock --no-update

install :
	poetry install --no-interaction

init: env install
update : update-lock install