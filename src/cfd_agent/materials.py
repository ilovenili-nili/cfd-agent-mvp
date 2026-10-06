import math

SATURATION_SOURCE = 'IAPWS Supplementary Release on Saturation Properties of Ordinary Water Substance (1992), vapor-pressure equation'

def water_saturation_pressure(temperature):
    """IAPWS saturation pressure in Pa; triple point to critical point."""
    if not 273.16<=temperature<=647.096:
        raise ValueError('Saturation correlation outside triple-to-critical-point range')
    tau=1-temperature/647.096
    coefficients=(-7.85951783,1.84408259,-11.7866497,22.6807411,-15.9618719,1.80122502)
    powers=(1,1.5,3,3.5,4,7.5)
    return 22.064e6*math.exp(647.096/temperature*sum(a*tau**b for a,b in zip(coefficients,powers)))
