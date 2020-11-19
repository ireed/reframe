# Copyright 2016-2020 Swiss National Supercomputing Centre (CSCS/ETH Zurich)
# ReFrame Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import ast
import os
import reframe as rfm
import reframe.utility.sanity as sn


class GridToolsBuildCheck(rfm.CompileOnlyRegressionTest):
    def __init__(self):
        self.valid_prog_environs = ['builtin']
        self.modules = ['CMake', 'Boost']
        self.valid_systems = ['daint:gpu', 'dom:gpu']

        self.sourcesdir = 'https://github.com/GridTools/gridtools.git'
        self.build_system = 'CMake'
        self.build_system.config_opts = [
            '-DCMAKE_CXX_FLAGS=-std=c++14',
            '-DCMAKE_CXX_COMPILER=CC',
            '-DCMAKE_C_COMPILER=cc',
            '-DCMAKE_Fortran_COMPILER=ftn',
            '-DGT_TESTS_REQUIRE_FORTRAN_COMPILER=ON',
            '-DGT_TESTS_REQUIRE_C_COMPILER=ON',
            '-DGT_TESTS_REQUIRE_OpenMP="ON"'
        ]
        self.build_system.flags_from_environ = False
        self.build_system.make_opts = ['perftests']
        self.build_system.max_concurrency = 2
        self.postbuild_cmds = ['ls tests/regression/']
        self.sanity_patterns = sn.assert_found(r'perftest',
                                               self.stdout)
        self.tags = {'scs', 'benchmark'}
        self.maintainers = ['CB']


@rfm.simple_test
class GridToolsCPUBuildCheck(GridToolsBuildCheck):
    def __init__(self):
        super().__init__()
        self.descr = 'GridTools CPU build test'
        self.build_system.config_opts += [
            '-DGT_TESTS_REQUIRE_GPU="OFF"'
        ]
        self.valid_systems += ['daint:mc', 'dom:mc']


@rfm.simple_test
class GridToolsGPUBuildCheck(GridToolsBuildCheck):
    def __init__(self):
        super().__init__()
        self.descr = 'GridTools GPU build test'
        self.modules.append('cudatoolkit')
        self.build_system.config_opts += [
            '-DGT_CUDA_ARCH=sm_60',
            '-DGT_TESTS_REQUIRE_GPU="ON"'
        ]


class GridToolsRunCheck(rfm.RunOnlyRegressionTest):
    def __init__(self):
        self.valid_prog_environs = ['builtin']
        self.modules = ['CMake', 'Boost']
        self.valid_systems = ['daint:gpu', 'dom:gpu']
        self.num_tasks = 1
        self.sanity_patterns = sn.assert_found(r'PASSED', self.stdout)
        self.perf_patterns = {
            'timer': sn.extractsingle(r'"series" : \[(?P<timer>\S+)\]',
                                      self.stdout, 'timer', float)
        }
        self.perf_patterns = {
            'timer': extract_avg(self.stdout)
        }


@sn.sanity_function
def extract_avg(data):
    return sn.avg(ast.literal_eval(str(sn.extractsingle(
                  r'"series" : \[(?P<timers>.+)\]', data, 'timers', str))))


@rfm.parameterized_test(['horizontal_diffusion/cpu_kfirst_double'],
                        ['horizontal_diffusion/cpu_ifirst_double'])
class GridToolsCPURunCheck(GridToolsRunCheck):
    def __init__(self, variant):
        super().__init__()
        self.descr = 'GridTools CPU run test'
        self.depends_on('GridToolsCPUBuildCheck')
        self.valid_systems += ['daint:mc', 'dom:mc']
        self.num_gpus_per_node = 0
        self.variant_data = {
            'horizontal_diffusion/cpu_kfirst_double': {
                'executable_opts': [
                    '256', '256', '80', '3',
                    '--gtest_filter=horizontal_diffusion/cpu_kfirst_double*'
                ],
                'reference': {
                    'daint:mc': {
                        'timer': (11.0, None, 0.1, 's')
                    },
                    'daint:gpu': {
                        'timer': (1.0, None, 0.1, 's')
                    },
                    'dom:mc': {
                        'timer': (11.0, None, 0.1, 's')
                    },
                    'dom:gpu': {
                        'timer': (1.0, None, 0.1, 's')
                    }
                }
            },
            'horizontal_diffusion/cpu_ifirst_double': {
                'executable_opts': [
                    '256', '256', '80', '3',
                    '--gtest_filter=horizontal_diffusion/cpu_ifirst_double*'
                ],
                'reference': {
                    'daint:mc': {
                        'timer': (9.0, None, 0.1, 's')
                    },
                    'daint:gpu': {
                        'timer': (1.0, None, 0.1, 's')
                    },
                    'dom:mc': {
                        'timer': (9.0, None, 0.1, 's')
                    },
                    'dom:gpu': {
                        'timer': (1.0, None, 0.1, 's')
                    }
                }
            }
        }
        self.executable_opts = self.variant_data[variant]['executable_opts']
        self.reference = self.variant_data[variant]['reference']
        self.tags = {'scs', 'benchmark'}
        self.maintainers = ['CB']

    @rfm.require_deps
    def set_executable(self, GridToolsCPUBuildCheck):
        self.executable = os.path.join(
            GridToolsCPUBuildCheck().stagedir,
            'tests', 'regression', 'perftests'
        )


@rfm.parameterized_test(['horizontal_diffusion/gpu_double'],
                        ['horizontal_diffusion/gpu_horizontal_double'])
class GridToolsGPURunCheck(GridToolsRunCheck):
    def __init__(self, variant):
        super().__init__()
        self.descr = 'GridTools GPU run test'
        self.depends_on('GridToolsGPUBuildCheck')
        self.modules.append('cudatoolkit')
        self.num_gpus_per_node = 1
        self.variant_data = {
            'horizontal_diffusion/gpu_double': {
                'executable_opts': [
                    '512', '512', '160', '3',
                    '--gtest_filter=horizontal_diffusion/gpu_double*'
                ],
                'reference': {
                    'daint:gpu': {
                        'timer': (0.004, None, 0.1, 's')
                    },
                    'dom:gpu': {
                        'timer': (0.004, None, 0.1, 's')
                    }
                }
            },
            'horizontal_diffusion/gpu_horizontal_double': {
                'executable_opts': [
                    '512', '512', '160', '3',
                    '--gtest_filter=horizontal_diffusion/gpu_horizontal_double*'
                ],
                'reference': {
                    'daint:gpu': {
                        'timer': (0.003, None, 0.1, 's')
                    },
                    'dom:gpu': {
                        'timer': (0.003, None, 0.1, 's')
                    }
                }
            }
        }
        self.executable_opts = self.variant_data[variant]['executable_opts']
        self.reference = self.variant_data[variant]['reference']
        self.tags = {'scs', 'benchmark'}
        self.maintainers = ['CB']

    @rfm.require_deps
    def set_executable(self, GridToolsGPUBuildCheck):
        self.executable = os.path.join(
            GridToolsGPUBuildCheck().stagedir,
            'tests', 'regression', 'perftests')
