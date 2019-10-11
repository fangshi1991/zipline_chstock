from distutils.core import setup,Extension
from Cython.Build import cythonize
import numpy 

setup(
    ext_modules = [Extension('_adjustments',['_adjustments.c'],
					include_dirs = [numpy.get_include()]
	)],
     )
setup(
    ext_modules=cythonize('_adjustments.pyx'),
	include_dirs = [numpy.get_include()]
)

'''
setup(
    ext_modules=cythonize('_adjustments.pyx'),
	include_dirs = [numpy.get_include()]
)'''
