'''
File: TL_Copasi.py
Project: ThinLayers
Author: Jan Range
License: BSD-2 clause
-----
Last Modified: Wednesday June 23rd 2021 10:25:11 pm
Modified By: Jan Range (<jan.range@simtech.uni-stuttgart.de>)
-----
Copyright (c) 2021 Institute of Biochemistry and Technical Biochemistry Stuttgart
'''

from typing import Union

from pyenzyme.enzymeml.core.enzymemldocument import EnzymeMLDocument
from pyenzyme.enzymeml.core import Replicate
from pyenzyme.enzymeml.core.enzymereaction import EnzymeReaction
from pyenzyme.enzymeml.models import MichaelisMenten
import os

import COPASI
from builtins import enumerate


class ThinLayerCopasi(object):

    def modelEnzymeML(
        self,
        reaction_id: str,
        protein_id: str,
        reactants: list[str],
        path: str,
        outdir: str = None
    ):
        """ThinLayer interface from an OMEX EnzymeML container to COPASI compatible CPS file format.

        Args:
            reaction_id (str): Measurement ID from which the data is used for modeling.
            protein_id (str): The ID of the protein that is catalysing the reaction.
            reactants (list[str]): The IDs of the modeled reactants.
            path (str): Path to the OMEX EnzymeML file.
            outdir (str, optional): Path to store the CPS COPASI file. Defaults to None.
        """

        # Save path in variable
        path = os.path.normpath(path)
        enzmldoc = EnzymeMLDocument.fromFile(path)

        # store files in the output dir unless not specified (in that case use
        # the directory from the example)
        if outdir is None:
            outdir = os.path.dirname(path)

        # Create directory for modeled data
        dirpath = os.path.join(outdir, f"Modeled_{reaction_id}")
        os.makedirs(dirpath, exist_ok=True)

        # Estimate parameters
        # TODO estimate kcat rather than vmax
        km_val, km_unit, vmax_val, vmax_unit = self.importEnzymeML(
            reaction_id,
            reactants,
            dirpath,
            enzmldoc
        )

        # TODO generalize to multiple reactants/proteins
        # ? Specific classmethods maybe to streamline known models?
        menten_model = MichaelisMenten(
            kcat_val=vmax_val,
            kcat_unit=vmax_unit,
            km_val=km_val,
            km_unit=km_unit,
            substrate_id=reactants[0],
            protein_id=protein_id,
            enzmldoc=enzmldoc
        )

        # Write model to reaction
        enzmldoc.reaction_dict[reaction_id].model = menten_model

        enzmldoc.toFile(dirpath)

    def importEnzymeML(
        self,
        reaction_id: str,
        reactants: Union[list[str], str],
        dirpath,
        enzmldoc
    ) -> tuple[float, str, float, str]:
        '''
        ThinLayer interface from an .omex EnzymeML container
        to COPASI comatible .cps file format.

        Args:
            String path: Path to .omex EnzymeML file
            String outdir: Path to store .cps COPASI file
            String reaction: Reaction ID to extract data from
            String reactants: Single or multiple IDs for desired reactant(s)
        '''

        if isinstance(reactants, str):
            reactants = [reactants]

        # Get reaction and replicates
        reaction = enzmldoc.getReaction(reaction_id)

        # Set up the kind of unit and scale the measurements will be set to
        # ? Exponent and multiplier also important
        kind = "mole"
        scale = -3

        # initialize COPASI data model
        dm = COPASI.CRootContainer.addDatamodel()
        sbml = enzmldoc.toXMLString()
        dm.importSBMLFromString(sbml)

        # COPASI

        # Get Reactant specific ConcentrationReference
        col_cn_map = {
            metab.sbml_id: metab.getConcentrationReference().getCN()
            for metab in dm.getModel().getMetabolites()
            if metab.sbml_id in reactants
        }

        # Describe .tsv file and call COPASI bindings
        task = dm.getTask('Parameter Estimation')
        task.setScheduled(True)
        problem = task.getProblem()
        problem.setCalculateStatistics(False)
        exp_set = problem.getExperimentSet()

        for reactant in reactants:

            # include each replicate
            for i, repl in enumerate(reaction.getEduct(reactant)[3]):

                data = repl.getData()
                speciesID = repl.getReactant()

                concVal, concUnit = enzmldoc.getConcDict()[repl.getInitConc()]
                timeUnit = repl.getTimeUnit()
                metab = [
                    metab
                    for metab in dm.getModel().getMetabolites()
                    if metab.sbml_id == reactant
                ][0]

                cn = metab.getInitialConcentrationReference().getCN()

                # TSV path
                tsvpath = os.path.join(
                    dirpath,
                    f'experiment_{reactant}_{i}.tsv'
                )

                data.to_csv(tsvpath,
                            sep='\t', header=True)

                exp = COPASI.CExperiment(dm)
                exp.setObjectName(
                    '{0} at {1:.2f}'.format(metab.getObjectName(), concVal)
                )
                exp.setFirstRow(1)
                exp.setLastRow(data.shape[0] + 1)
                exp.setHeaderRow(1)
                exp.setFileName(tsvpath)
                exp.setExperimentType(COPASI.CTaskEnum.Task_timeCourse)
                exp.setSeparator('\t')
                exp.setNumColumns(2)
                exp = exp_set.addExperiment(exp)
                info = COPASI.CExperimentFileInfo(exp_set)
                info.setFileName(tsvpath)

                # add the initial concentration as fit item
                item = problem.addFitItem(cn)
                item.setStartValue(concVal)
                item.setLowerBound(COPASI.CCommonName(str(concVal * 0.01)))
                item.setUpperBound(COPASI.CCommonName(str(concVal * 100)))
                item.addExperiment(exp.getKey())

                # Mapping from .tsv file to COPASI bindings
                obj_map = exp.getObjectMap()
                obj_map.setNumCols(2)

                for i, col in enumerate(["time"] + [speciesID]):
                    if col == "time":
                        role = COPASI.CExperiment.time
                        obj_map.setRole(i, role)

                    elif col in col_cn_map.keys():
                        role = COPASI.CExperiment.dependent
                        obj_map.setRole(i, role)
                        obj_map.setObjectCN(i, col_cn_map[col])

                    else:
                        role = COPASI.CExperiment.ignore
                        obj_map.setRole(i, role)

        # Finally save the model and add plot/progress
        task = dm.getTask('Parameter Estimation')
        task.setMethodType(COPASI.CTaskEnum.Method_Statistics)
        COPASI.COutputAssistant.getListOfDefaultOutputDescriptions(task)
        COPASI.COutputAssistant.createDefaultOutput(913, task, dm)
        COPASI.COutputAssistant.createDefaultOutput(911, task, dm)

        # Gather Menten parameters
        km_value, vmax_value = self.run_parameter_estimation(dm)
        km_unit = enzmldoc.getUnitDict()[concUnit].getName()
        timeUnit = enzmldoc.getUnitDict()[timeUnit].getName()

        if "M" in km_unit:
            vmax_unit = km_unit + ' / ' + timeUnit
        else:
            split_u = km_unit.split('/')
            vmax_unit = split_u[0] + ' / ' + f'( {split_u[1]} * {timeUnit} )'

        return (km_value, km_unit, vmax_value, vmax_unit)

    def unifyUnits(
        self,
        reactant: str,
        reaction: EnzymeReaction,
        enzmldoc: 'EnzymeMLDocument',
        kind
    ):

        # get unit of specified reactant
        unit = enzmldoc.getReactant(reactant)._unit_id
        unit = enzmldoc.unit_dict[unit]
        units = unit.units
        scale = next(filter(
            lambda base_unit: base_unit.kind == kind,
            units
        ))

        # iterate through elements
        reaction_elements = [
            *reaction.educts,
            *reaction.products,
            *reaction.modifiers
        ]

        for index, reaction_element in enumerate(reaction_elements):
            for tup in elem:

                # get exponent and scale to calculate
                # factor for new calculation
                if tup[0][0] == 's':
                    unit_r = enzmldoc.getUnitDict()[
                        enzmldoc.getReactant(tup[0]).getSubstanceUnits()
                    ]

                if tup[0][0] == 'p':
                    unit_r = enzmldoc.getUnitDict()[
                        enzmldoc.getProtein(tup[0]).getSubstanceUnits()
                    ]

                units_r = unit_r.getUnits()
                exponent_r = [tup[1] for tup in units_r if tup[0] == kind][0]
                scale_r = [tup[2] for tup in units_r if tup[0] == kind][0]

                nu_scale = exponent_r * (scale_r - scale)

                if nu_scale != 0:

                    # Reset Species initial concentrations
                    if tup[0][0] == 's':

                        enzmldoc.getReactant(tup[0]).setSubstanceUnits(
                            unit.getId()
                        )
                        enzmldoc.getReactant(tup[0]).setInitConc(
                            enzmldoc.getReactant(
                                tup[0]).getInitConc() * (10**nu_scale)
                        )

                    elif tup[0][0] == 'p':

                        enzmldoc.getProtein(tup[0]).setSubstanceUnits(
                            unit.getId()
                        )

                        enzmldoc.getProtein(tup[0]).setInitConc(
                            enzmldoc.getProtein(
                                tup[0]).getInitConc() * (10**nu_scale)
                        )

                    # Reset replicate concentrations
                    nu_repls = [
                        Replicate(
                            replica=repl.getReplica(),
                            reactant=repl.getReactant(),
                            type_=repl.getType(),
                            data_unit=unit.getId(),
                            time_unit=repl.getTimeUnit(),
                            init_conc=repl.getInitConc() * (10**nu_scale),
                            measurement=repl.getMeasurement()
                        )

                        for repl in tup[3]
                    ]

                    # Reset initial concentrations
                    nu_inits = list()
                    for initValue, initUnit in tup[4]:
                        nu_conc = initValue * (10**nu_scale)
                        nu_inits.append((nu_conc, initUnit))
                        enzmldoc.addConc((nu_conc, initUnit))

                    # Remove old element
                    elementTuple = (tup[0], tup[1], tup[2], nu_repls, nu_inits)

                    if i == 0:
                        reaction.getEducts()[
                            reaction.getEduct(tup[0], index=True)
                        ] = elementTuple
                    if i == 1:
                        reaction.getProducts()[
                            reaction.getProduct(tup[0], index=True)
                        ] = elementTuple
                    if i == 2:
                        reaction.getModifiers()[
                            reaction.getModifier(tup[0], index=True)
                        ] = elementTuple

    ##### COPASI FUNCTIONS #####

    def replace_kinetic_law(self, dm, reaction, function_name):
        # type: (COPASI.CDataModel, COPASI.CReaction, str) -> None
        functions = COPASI.CRootContainer.getFunctionList()
        function = functions.findFunction(function_name)
        if function is None:
            print("No such function defined, can't change kinetics")
            return

        if reaction.isReversible():  # for now force the kinetic to be irreversible
            # (otherwise the kinetic law does not apply)
            reaction.setReversible(False)

        # now since we have 2 substrates in this case and we would automatically assign the first substrate
        # to the new function, we want to make sure that we map to the same substrates as the old reaction
        substrates = None
        fun_params = reaction.getFunctionParameters()
        for i in range(fun_params.size()):
            param = fun_params.getParameter(i)
            if param.getUsage() == COPASI.CFunctionParameter.Role_SUBSTRATE:
                substrates = reaction.getParameterCNs(param.getObjectName())
                break

        # set the new function
        reaction.setFunction(function)
        if substrates is not None:
            # in case we found substrates map them
            reaction.setParameterCNs('substrate', substrates)

        # recompile model so it can be simulated later on
        reaction.compile()
        dm.getModel().forceCompile()
        pass

    def run_parameter_estimation(self, dm):
        task = dm.getTask('Parameter Estimation')
        assert (isinstance(task, COPASI.CFitTask))
        task.setScheduled(True)
        problem = task.getProblem()
        problem.setCalculateStatistics(False)
        # problem.setRandomizeStartValues(True)  # not randomizing this time

        reaction = dm.getModel().getReaction(0)
        self.replace_kinetic_law(
            dm,
            reaction,
            "Henri-Michaelis-Menten (irreversible)"
        )
        objects = reaction.getParameterObjects()

        cn_name_map = {}

        # add fit items for reaction parameters
        for obj in objects:
            param = obj[0]
            if param.getObjectAncestor('Reaction') is None:
                # skip all non-local parameters
                continue
            value = reaction.getParameterValue(param.getObjectName())
            item = problem.addFitItem(param.getValueObject().getCN())
            item.setStartValue(value)  # the current initial concentration
            item.setLowerBound(COPASI.CCommonName(str(value * 0.0001)))
            item.setUpperBound(COPASI.CCommonName(str(value * 10000)))
            cn_name_map[param.getValueObject().getCN().getString()
                        ] = param.getObjectName()

        # switch optimization method
        task.setMethodType(COPASI.CTaskEnum.Method_LevenbergMarquardt)

        # run optimization
        task.initialize(COPASI.CCopasiTask.OUTPUT_UI)
        task.process(True)

        # print parameter values
        assert (isinstance(problem, COPASI.CFitProblem))
        results = problem.getSolutionVariables()

        vmax = None
        km = None

        for i in range(problem.getOptItemSize()):
            item = problem.getOptItem(i)
            cn = item.getObjectCN().getString()
            if cn not in cn_name_map:
                continue
            value = results.get(i)

            if cn_name_map[cn] == 'V':
                vmax = value
            if cn_name_map[cn] == 'Km':
                km = value

        return km, vmax


if __name__ == '__main__':
    path = os.path.join('COPASI', '3IZNOK_TEST.omex')
    ThinLayerCopasi().modelEnzymeML('r0', 's1', path)
