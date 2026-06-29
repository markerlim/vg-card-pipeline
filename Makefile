SET_CODE ?= VGE-DZ-BT14
SET_NAME ?= Envoys of the Crimson Moon
SET_URL  ?= https://cardfight.fandom.com/wiki/DZ_Booster_Set_14:_Envoys_of_the_Crimson_Moon

.PHONY: new-set

new-set:
	@echo "=== Adding set to wiki_sets.json ==="
	python3 scripts/add_set.py "$(SET_CODE)" "$(SET_NAME)" "$(SET_URL)"
	@echo "=== Running pipeline ==="
	python3 main.py --set $(SET_CODE)
	@echo "=== Running Shopify export ==="
	python3 functions/shopify_export.py
