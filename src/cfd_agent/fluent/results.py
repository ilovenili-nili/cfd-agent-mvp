import math
import re

def residuals_from_log(text):
    names=None; result={}
    for line in text.splitlines():
        words=line.split()
        if words and words[0]=='iter' and 'continuity' in words:
            names=words[1:]
        elif names and words and words[0].isdigit():
            for name,value in zip(names,words[1:]):
                if name in ['continuity','x-velocity','y-velocity','z-velocity','energy','k','omega']:
                    try: result[name]=float(value)
                    except ValueError: pass
    return result

class Reports:
    def __init__(self,session):
        self.session=session
        self.defs=session.settings.solution.report_definitions
        surfaces={'outlet_temperature':('surface-massavg','temperature',['mixed_outlet'])}
        for port in ['cold_inlet','hot_inlet','mixed_outlet']:
            surfaces['mass_'+port]=('surface-massflowrate','', [port])
            surfaces['temp_'+port]=('surface-massavg','temperature',[port])
        for name,(kind,field,zones) in surfaces.items():
            args={'report_type':kind,'surface_names':zones}
            if field: args['field']=field
            self.defs.surface[name]=args
        zones=session.settings.setup.cell_zone_conditions.fluid.get_object_names()
        for name,kind,field in [('temperature_min','volume-min','temperature'),('temperature_max','volume-max','temperature'),
                                ('velocity_max','volume-max','velocity-magnitude'),('pressure_min','volume-min','pressure'),
                                ('pressure_max','volume-max','pressure')]:
            self.defs.volume[name]={'report_type':kind,'field':field,'cell_zones':zones}
        self.names=list(surfaces)+['temperature_min','temperature_max','velocity_max','pressure_min','pressure_max']

    def sample(self):
        result=self.defs.compute(report_defs=self.names)
        # PyFluent generated API returns [report-value mapping, report metadata].
        mapping=result[0] if isinstance(result,(tuple,list)) else result
        out={}
        for name in self.names:
            value=mapping[name]
            while isinstance(value,(tuple,list)): value=value[0]
            out[name]=float(value)
            if not math.isfinite(out[name]): raise RuntimeError('Non-finite report '+name)
        return out

    def finalize(self,data):
        ports=['cold_inlet','hot_inlet','mixed_outlet']
        total=sum(abs(data['mass_'+p]) for p in ports[:2])
        if total<=0: raise RuntimeError('Zero inlet mass flow')
        data['mass_imbalance_fraction']=abs(sum(data['mass_'+p] for p in ports))/total
        # Constant cp cancels; reference-relative sensible enthalpy avoids arbitrary zero dependence.
        ref=273.15
        denom=sum(abs(data['mass_'+p]*(data['temp_'+p]-ref)) for p in ports[:2])
        data['energy_imbalance_fraction']=abs(sum(data['mass_'+p]*(data['temp_'+p]-ref) for p in ports))/max(denom,1e-12)
        return data
