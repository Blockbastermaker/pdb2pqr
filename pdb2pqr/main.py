"""Driver for PDB2PQR

This module takes a PDB file as input and performs optimizations before yielding a new PDB-style file as output.
"""

# TODO - would be nice to remove os package
import os
import logging
from pathlib import Path
from . import cli
from . import run
from . import pdb, cif, utilities, structures
from .errors import PDB2PQRError
from .propka import lib as propka_lib
from . import extensions
from . import __version__
from .pdb2pka.ligandclean import ligff


HEADER_TEXT = """
----------------------------------------------------
PDB2PQR - biomolecular structure conversion software
Version {version}
----------------------------------------------------
Please cite your use of PDB2PQR as:

  Dolinsky TJ, Nielsen JE, McCammon JA, Baker NA. PDB2PQR: an automated
  pipeline for the setup, execution, and analysis of Poisson-Boltzmann
  electrostatics calculations. Nucleic Acids Research 32 W665-W667 (2004).
"""
HEADER_TEXT = HEADER_TEXT.format(version=__version__)
_LOGGER = logging.getLogger(__name__)
logging.captureWarnings(True)


def mainCommand():
    """Main driver for running program from the command line."""

    parser = cli.build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    _LOGGER.debug("Args:  %s", args)
    _LOGGER.info(HEADER_TEXT)

    if args.assign_only or args.clean:
        args.debump = False
        args.opt = False

    if not args.clean:
        if args.usernames is not None:
            # TODO - it makes me sad to open a file without a close() statement
            user_names_file = open(args.usernames, 'rt', encoding="utf-8")
        if args.userff is not None:
            # TODO - it makes me sad to open a file without a close() statement
            user_ff_file = open(args.userff, "rt", encoding="utf-8")
            if args.usernames is None:
                parser.error(message='--usernames must be specified if using --userff')
        if utilities.getFFfile(args.ff) == "":
            parser.error(message="Unable to load parameter file for forcefield %s" % args.ff)
        if (args.ph < 0) or (args.ph > 14):
            parser.error(message="Specified pH (%s) is outside the range [1, 14] of this program" % args.ph)
    
    ph_calc_options = None

    if args.pka_method == 'propka':
        ph_calc_options, _ = propka_lib.loadOptions('--quiet')
    elif args.pka_method == 'pdb2pka':
        if args.ff.lower() != 'parse':
            parser.error('PDB2PKA requires the PARSE force field.')
        ph_calc_options = {'output_dir': args.output_pqr,
                          'clean_output': not args.pdb2pka_resume,
                          'pdie': args.pdie,
                          'sdie': args.sdie,
                          'pairene': args.pairene}

    if args.ligand is not None:
        try:
            # TODO - it makes me sad to open a file without a close() statement
            ligand_file = open(args.ligand, 'rt', encoding="utf-8")
        except IOError:
            parser.error('Unable to find ligand file %s!' % args.ligand)

    if args.neutraln and (args.ff is None or args.ff.lower() != 'parse'):
        parser.error('--neutraln option only works with PARSE forcefield!')

    if args.neutralc and (args.ff is None or args.ff.lower() != 'parse'):
        parser.error('--neutralc option only works with PARSE forcefield!')


    path = Path(args.input_pdb)
    pdbFile = utilities.getPDBFile(args.input_pdb)

    args.isCIF = False
    if path.suffix.lower() == "cif":
        pdblist, errlist = cif.readCIF(pdbFile)
        args.isCIF = True
    else:
        pdblist, errlist = pdb.readPDB(pdbFile)

    if len(pdblist) == 0 and len(errlist) == 0:
        parser.error("Unable to find file %s!" % path)

    if len(errlist) != 0:
        if(isCIF):
            _LOGGER.warn("Warning: %s is a non-standard CIF file.\n", path)
        else:
            _LOGGER.warn("Warning: %s is a non-standard PDB file.\n", path)
        _LOGGER.error(errlist)

    args.outname = args.output_pqr

    # In case no extensions were specified or no extensions exist.
    # TODO - there are no command line options for extensions so I'm not sure what this does
    if not hasattr(args, 'active_extensions'):
        args.active_extensions = []
    elif args.active_extensions is None:
        args.active_extensions = []
    extensionOpts = args

    try:
        results_dict = run.runPDB2PQR(pdblist, args)
        header = results_dict["header"]
        lines = results_dict["lines"]
        missedligands = results_dict["missed_ligands"]
    except PDB2PQRError as error:
        _LOGGER.error(error)
        raise PDB2PQRError(error)

    # Print the PQR file
    # TODO - move this to another function... this function is already way too long.
    outfile = open(args.output_pqr,"w")
    outfile.write(header)
    # Adding whitespaces if --whitespace is in the options
    for line in lines:
        if args.whitespace:
            if line[0:4] == 'ATOM':
                newline = line[0:6] + ' ' + line[6:16] + ' ' + line[16:38] + ' ' + line[38:46] + ' ' + line[46:]
                outfile.write(newline)
            elif line[0:6] == 'HETATM':
                newline = line[0:6] + ' ' + line[6:16] + ' ' + line[16:38] + ' ' + line[38:46] + ' ' + line[46:]
                outfile.write(newline)
            elif line[0:3] == "TER" and args.isCIF:
                pass
        else:
            if line[0:3] == "TER" and args.isCIF:
                pass
            else:
                outfile.write(line)
    if(args.isCIF):
        outfile.write("#\n")
    outfile.close()

    if args.apbs_input:
        from src import inputgen
        from src import psize
        method = "mg-auto"
        size = psize.Psize()
        size.parseInput(args.output_pqr)
        size.runPsize(args.output_pqr)
        #async = 0 # No async files here!
        input = inputgen.Input(args.output_pqr, size, method, 0, potdx=True)
        input.printInputFiles()
        input.dumpPickle()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logging.captureWarnings(True)
    mainCommand()