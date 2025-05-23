import copy

from pytest import approx, raises, fixture

from h2integrate.simulation.technologies.steel import steel


ng_prices_dict = {
    "2035": 3.76232,
    "2036": 3.776032,
    "2037": 3.812906,
    "2038": 3.9107960000000004,
    "2039": 3.865776,
    "2040": 3.9617400000000003,
    "2041": 4.027136,
    "2042": 4.017166,
    "2043": 3.9715339999999997,
    "2044": 3.924314,
    "2045": 3.903287,
    "2046": 3.878192,
    "2047": 3.845413,
    "2048": 3.813366,
    "2049": 3.77735,
    "2050": 3.766164,
    "2051": 3.766164,
    "2052": 3.766164,
    "2053": 3.766164,
    "2054": 3.766164,
    "2055": 3.766164,
    "2056": 3.766164,
    "2057": 3.766164,
    "2058": 3.766164,
    "2059": 3.766164,
    "2060": 3.766164,
    "2061": 3.766164,
    "2062": 3.766164,
    "2063": 3.766164,
    "2064": 3.766164,
}
grid_prices_dict = {
    "2035": 89.42320514456621,
    "2036": 89.97947569251141,
    "2037": 90.53574624045662,
    "2038": 91.09201678840184,
    "2039": 91.64828733634704,
    "2040": 92.20455788429224,
    "2041": 89.87291235917809,
    "2042": 87.54126683406393,
    "2043": 85.20962130894978,
    "2044": 82.87797578383562,
    "2045": 80.54633025872147,
    "2046": 81.38632144593608,
    "2047": 82.22631263315068,
    "2048": 83.0663038203653,
    "2049": 83.90629500757991,
    "2050": 84.74628619479452,
    "2051": 84.74628619479452,
    "2052": 84.74628619479452,
    "2053": 84.74628619479452,
    "2054": 84.74628619479452,
    "2055": 84.74628619479452,
    "2056": 84.74628619479452,
    "2057": 84.74628619479452,
    "2058": 84.74628619479452,
    "2059": 84.74628619479452,
    "2060": 84.74628619479452,
    "2061": 84.74628619479452,
    "2062": 84.74628619479452,
    "2063": 84.74628619479452,
    "2064": 84.74628619479452,
}

financial_assumptions = {
    "total income tax rate": 0.2574,
    "capital gains tax rate": 0.15,
    "leverage after tax nominal discount rate": 0.10893,
    "debt equity ratio of initial financing": 0.624788,
    "debt interest rate": 0.050049,
}


@fixture
def cost_config():
    config = steel.SteelCostModelConfig(
        operational_year=2035,
        plant_capacity_mtpy=1084408.2137715619,
        lcoh=4.2986685034417045,
        feedstocks=steel.Feedstocks(natural_gas_prices=ng_prices_dict, oxygen_market_price=0),
        o2_heat_integration=False,
    )
    return config


def test_run_steel_model():
    capacity = 100.0
    capacity_factor = 0.9

    steel_production_mtpy = steel.run_steel_model(capacity, capacity_factor)

    assert steel_production_mtpy == 90.0


def test_steel_cost_model(subtests, cost_config):
    res: steel.SteelCostModelOutputs = steel.run_steel_cost_model(cost_config)

    with subtests.test("CapEx"):
        assert res.total_plant_cost == approx(617972269.2565368)
    with subtests.test("Fixed OpEx"):
        assert res.total_fixed_operating_cost == approx(104244740.28004119)
    with subtests.test("Installation"):
        assert res.installation_cost == approx(209403678.7623758)


def test_steel_finance_model(cost_config):
    # Parameter -> Hydrogen/Steel/Ammonia
    costs: steel.SteelCostModelOutputs = steel.run_steel_cost_model(cost_config)

    plant_capacity_factor = 0.9
    steel_production_mtpy = steel.run_steel_model(
        cost_config.plant_capacity_mtpy, plant_capacity_factor
    )

    config = steel.SteelFinanceModelConfig(
        plant_life=30,
        plant_capacity_mtpy=cost_config.plant_capacity_mtpy,
        plant_capacity_factor=plant_capacity_factor,
        steel_production_mtpy=steel_production_mtpy,
        lcoh=cost_config.lcoh,
        feedstocks=cost_config.feedstocks,
        grid_prices=grid_prices_dict,
        financial_assumptions=financial_assumptions,
        costs=costs,
    )

    lcos_expected = 1003.6498479621724

    res: steel.SteelFinanceModelOutputs = steel.run_steel_finance_model(config)

    assert res.sol.get("price") == lcos_expected


def test_steel_size_h2_input(subtests):
    config = steel.SteelCapacityModelConfig(
        hydrogen_amount_kgpy=73288888.8888889,
        input_capacity_factor_estimate=0.9,
        feedstocks=steel.Feedstocks(natural_gas_prices=ng_prices_dict, oxygen_market_price=0),
    )

    res: steel.SteelCapacityModelOutputs = steel.run_size_steel_plant_capacity(config)

    with subtests.test("steel plant size"):
        assert res.steel_plant_capacity_mtpy == approx(1000000)
    with subtests.test("hydrogen input"):
        assert res.hydrogen_amount_kgpy == approx(73288888.8888889)


def test_steel_size_steel_input(subtests):
    config = steel.SteelCapacityModelConfig(
        desired_steel_mtpy=1000000,
        input_capacity_factor_estimate=0.9,
        feedstocks=steel.Feedstocks(natural_gas_prices=ng_prices_dict, oxygen_market_price=0),
    )

    res: steel.SteelCapacityModelOutputs = steel.run_size_steel_plant_capacity(config)

    with subtests.test("steel plant size"):
        assert res.steel_plant_capacity_mtpy == approx(1111111.111111111)
    with subtests.test("hydrogen input"):
        assert res.hydrogen_amount_kgpy == approx(73288888.8888889)


def test_run_steel_full_model(subtests):
    config = {
        "steel": {
            "capacity": {
                "input_capacity_factor_estimate": 0.9,
                "desired_steel_mtpy": 1000000,
            },
            "costs": {
                "operational_year": 2035,
                "o2_heat_integration": False,
                "feedstocks": {
                    "natural_gas_prices": ng_prices_dict,
                    "oxygen_market_price": 0,
                },
                "lcoh": 4.2986685034417045,
            },
            "finances": {
                "plant_life": 30,
                "lcoh": 4.2986685034417045,
                "grid_prices": grid_prices_dict,
                "financial_assumptions": financial_assumptions,
            },
        }
    }

    res = steel.run_steel_full_model(config)

    with subtests.test("output length"):
        assert len(res) == 3

    with subtests.test("h2 mass per year"):
        assert res[0].hydrogen_amount_kgpy == approx(73288888.8888889)

    with subtests.test("plant cost"):
        assert res[1].total_plant_cost == approx(627667493.7760644)
    with subtests.test("Installation"):
        assert res[1].installation_cost == approx(212913296.16069925)
    with subtests.test("steel price"):
        assert res[2].sol.get("price") == approx(1000.0534906485253)


def test_run_steel_full_model_changing_lcoh(subtests):
    config_0 = {
        "steel": {
            "capacity": {
                "input_capacity_factor_estimate": 0.9,
                "desired_steel_mtpy": 1000000,
            },
            "costs": {
                "operational_year": 2035,
                "o2_heat_integration": False,
                "feedstocks": {
                    "natural_gas_prices": ng_prices_dict,
                    "oxygen_market_price": 0,
                },
                "lcoh": 4.2986685034417045,
            },
            "finances": {
                "plant_life": 30,
                "lcoh": 4.2986685034417045,
                "grid_prices": grid_prices_dict,
                "financial_assumptions": financial_assumptions,
            },
        }
    }

    config_1 = copy.deepcopy(config_0)
    config_1["steel"]["costs"]["lcoh"] = 20.0
    config_1["steel"]["finances"]["lcoh"] = 20.0

    res0 = steel.run_steel_full_model(config_0)
    res1 = steel.run_steel_full_model(config_1)

    with subtests.test("output length 0"):
        assert len(res0) == 3
    with subtests.test("output length 1"):
        assert len(res1) == 3
    with subtests.test("res0 res1 equal h2 mass per year"):
        assert res0[0].hydrogen_amount_kgpy == res1[0].hydrogen_amount_kgpy
    with subtests.test("res0 res1 equal plant cost"):
        assert res0[1].total_plant_cost == res1[1].total_plant_cost
    with subtests.test("res0 price lt res1 price"):
        assert res0[2].sol.get("price") < res1[2].sol.get("price")
    with subtests.test("raise value error when LCOH values do not match"):
        config_1["steel"]["finances"]["lcoh"] = 40.0
        with raises(ValueError, match="steel cost LCOH and steel finance LCOH are not equal"):
            res1 = steel.run_steel_full_model(config_1)


def test_run_steel_full_model_changing_feedstock_transport_costs(subtests):
    config = {
        "steel": {
            "capacity": {
                "input_capacity_factor_estimate": 0.9,
                "desired_steel_mtpy": 1000000,
            },
            "costs": {
                "operational_year": 2035,
                "o2_heat_integration": False,
                "feedstocks": {
                    "natural_gas_prices": ng_prices_dict,
                    "oxygen_market_price": 0,
                    "lime_transport_cost": 47.72,
                    "carbon_transport_cost": 64.91,
                    "iron_ore_pellet_transport_cost": 0.63,
                },
                "lcoh": 4.2986685034417045,
            },
            "finances": {
                "plant_life": 30,
                "lcoh": 4.2986685034417045,
                "grid_prices": grid_prices_dict,
                "financial_assumptions": financial_assumptions,
            },
        }
    }

    res = steel.run_steel_full_model(config)

    with subtests.test("plant cost"):
        assert res[1].total_plant_cost == approx(627667493.7760644)

    with subtests.test("Installation"):
        assert res[1].installation_cost == approx(213896544.47120154)

    with subtests.test("steel price"):
        assert res[2].sol.get("price") == approx(1005.7008348727317)
