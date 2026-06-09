class BaseMaterialHeader:
    name = "名称"
    unit_price = "单价"
    moisture = "水分"
    burning_loss = "烧损"


class BlendHeader:
    name = "名称"
    low_bound = "下限"
    up_bound = "上限"
    baseline_ratio = "基准值配比"
    integrated_ratio = "一体化配比"
    unit_price = "单价"
    moisture = "水分"
    burning_loss = "烧损"
    baseline_dry_basis = "基准值干基量"
    integrated_dry_basis = "一体化干基量"
    baseline_burn_save = "基准值烧存"
    integrated_burn_save = "一体化烧存"


class BurdenHeader:
    selected = "勾选"
    category = "名称归属"
    name = "名称"
    low_bound = "下限"
    up_bound = "上限"
    baseline_ratio = "基准值配比"
    integrated_ratio = "一体化配比"
    unit_price = "单价"
    baseline_dry_unit = "基准值干基单耗"
    integrated_dry_unit = "一体化干基单耗"
    baseline_gross_dry_unit = "基准值干基毛单耗"
    integrated_gross_dry_unit = "一体化干基毛单耗"
    return_fines_price = "返粉单价"
    baseline_return_fines = "基准值干基返粉"
    integrated_return_fines = "一体化干基返粉"


class FuelRatioHeader:
    name = "名称"
    baseline_ratio = "基准值配比"
    integrated_ratio = "一体化配比"
    unit_price = "单价"
    baseline_dry_unit = "基准值干基单耗"
    integrated_dry_unit = "一体化干基单耗"
    baseline_gross_dry_unit = "基准值干基毛单耗"
    integrated_gross_dry_unit = "一体化干基毛单耗"
    baseline_return_fines = "基准值干基返粉"
    integrated_return_fines = "一体化干基返粉"


class BoundHeader:
    selected = "勾选"
    name = "名称"
    low_bound = "下限"
    up_bound = "上限"
    baseline_value = "基准值"
    integrated_value = "一体化"


class ParamHeader:
    name = "名称"
    value = "数值"
    unit = "单位"


class HotMetalCostHeader:
    baseline_cost = "基准值铁水成本"
    integrated_cost = "一体化铁水成本"
