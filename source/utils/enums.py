COMPONENTS = [
    "TFe", "CaO", "SiO2", "MgO", "Al2O3", "P", "S", "V2O5", "Cr",
    "TiO2", "Zn", "Ni", "MnO", "K2O", "Na2O", "Pb", "CuO", "FeO",
]

PRODUCT_COMPONENTS = [
    "TFe", "CaO", "SiO2", "MgO", "Al2O3", "P", "S", "V2O5", "Cr",
    "TiO2", "Zn", "Ni", "MnO", "K2O", "Na2O", "Pb", "CuO",
]

HOT_METAL_ROWS = [
    "Fe", "Ca", "Si", "Mg", "Al", "P", "S", "V", "Cr", "Ti", "Zn", "Ni",
    "Mn", "K", "Na", "Pb", "Cu",
]

HOT_METAL_TO_COMPONENT = dict(zip(HOT_METAL_ROWS, PRODUCT_COMPONENTS))

SINTER_INDICATORS = ["CaO/SiO2", "Al2O3/SiO2", "MgO/Al2O3"]
SLAG_ALKALINITIES = ["镁铝比", "二元碱度", "三元碱度", "四元碱度"]
HARMFUL_LOAD_COMPONENT = {
    "硫负荷": "S",
    "锌负荷": "Zn",
    "钛负荷": "TiO2",
    "钾负荷": "K2O",
    "钠负荷": "Na2O",
}

BURDEN_CATEGORY_SINTER = "烧结矿"
BURDEN_CATEGORY_PELLET = "球团矿"
BURDEN_CATEGORY_LUMP = "块矿"
INTEGRATED_SINTER_NAME = "一体化烧结矿"
INTEGRATED_PELLET_NAME = "一体化球团矿"
