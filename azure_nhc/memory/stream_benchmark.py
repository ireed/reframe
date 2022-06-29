# Copyright 2016-2021 Swiss National Supercomputing Centre (CSCS/ETH Zurich)
# ReFrame Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import os
import json as js
import re

import reframe as rfm
import reframe.utility.sanity as sn
import reframe.utility.udeps as udeps

# rfmdocstart: osupingpong
class StreamBenchmarkTestBase(rfm.RunOnlyRegressionTest):
    '''Base class of Stream benchmark runtime tests'''

    valid_systems = ['*:default']
    valid_prog_environs = ['gnu-azhpc']
    sourcesdir = None

    # rfmdocstart: set_deps
    @run_after('init')
    def set_dependencies(self):
        self.depends_on('StreamDownloadRunScriptsTest', udeps.by_env)
    # rfmdocend: set_deps

@rfm.simple_test
class StreamAllVMsTest(StreamBenchmarkTestBase):
    descr = 'Stream ALL VMs test using pssh'

    # rfmdocstart: set_exec
    @require_deps
    def set_sourcedir(self, StreamDownloadRunScriptsTest):
        self.sourcesdir = os.path.join(
            StreamDownloadRunScriptsTest(part='default', environ='gnu-azhpc').stagedir,
            ''
        )
    prerun_cmds = [
        'sh aocc-compiler-3.2.0/install.sh',
        'source ./setenv_AOCC.sh'
        ]
    executable = './stream_pssh_script.sh'
    postrun_cmds = [
        'list=($(ls -d stream-*)); for i in ${list[@]}; do cat $i/stream*.log; done',
        'cat stream-test-results.log',
    ]
    @run_before('run')
    def set_test_flags(self):
        vm_info = self.current_system.node_data
        vm_series = vm_info['vm_series'] 
        self.executable_opts = [ vm_series ]

    @run_before('run')
    def set_vm_series(self):
        vm_info = self.current_system.node_data
        vm_series = vm_info['vm_series']
        self.variables = {
            'VM_SERIES': vm_series
        }

    @sanity_function
    def assert_num_messages(self):
        num_tests = sn.len(sn.findall(r'stream: (\S+)',
                                         self.stagedir+'/stream-test-results.log'))
        num_nodes = sum(1 for _ in open(self.stagedir+'/hosts.txt'))
        return sn.assert_eq(num_tests, num_nodes)

    @performance_function('MB/s')
    def extract_stream_s(self, vm='c5e'):
         return sn.extractsingle(rf'system: {vm} stream: (\S+)',self.stagedir+'/stream-test-results.log', 1, float)

    @run_before('performance')
    def set_perf_variables(self):
        '''Build the dictionary with all the performance variables.'''

        self.perf_variables = {}
        with open(self.stagedir+'/stream-test-results.log',"r") as f:
            sys_names = f.read()

        systems = re.findall(r"system:\s(\S+)\s+.*",sys_names,re.M)
        stream = re.findall(r"stream: (\S+)",sys_names,re.M)

        vm_info = self.current_system.node_data
        vm_series = vm_info['vm_series']
        temp = {vm_series: {}}

        if vm_info != None and 'nhc_values' in vm_info:
            for i in systems:
                temp[vm_series][i] = (vm_info['nhc_values']['stream_triad'],
                                        vm_info['nhc_values']['stream_triad_limits'][0],
                                        vm_info['nhc_values']['stream_triad_limits'][1],
                                        'MB/s')

        self.reference = temp

        for i in systems:
            self.perf_variables[i] = self.extract_stream_s(i)

        results = {}
        for i in range(len(systems)):
            results[systems[i]] = stream[i]

        with open(self.outputdir+"/stream_test_results.json", "w") as outfile:
            js.dump(results, outfile, indent=4)

@rfm.simple_test
class StreamDownloadRunScriptsTest(rfm.RunOnlyRegressionTest):
    descr = 'Download stream run scripts test'
    valid_systems = ['*:default']
    valid_prog_environs = ['gnu-azhpc']
    executable = 'wget'
    executable_opts = [
        'https://raw.githubusercontent.com/arstgr/stream/main/stream_pssh_script.sh'  # noqa: E501
    ]
    postrun_cmds = [
        'wget https://raw.githubusercontent.com/arstgr/stream/main/stream_run_script.sh',
        'chmod +x stream_pssh_script.sh',
        'chmod +x stream_run_script.sh'
    ]

    @run_after('init')
    def inject_dependencies(self):
        self.depends_on('StreamBuildTest', udeps.fully)

    @require_deps
    def set_sourcedir(self, StreamBuildTest):
        self.sourcesdir = os.path.join(
            StreamBuildTest(part='default', environ='gnu-azhpc').stagedir,
            ''
        )

    @sanity_function
    def validate_download(self):
        return sn.assert_true(os.path.exists('stream_pssh_script.sh')) and sn.assert_true(os.path.exists('stream_run_script.sh'))

@rfm.simple_test
class StreamBuildTest(rfm.RunOnlyRegressionTest):
    descr = 'Stream benchmark build test'
    valid_systems = ['*:default']
    valid_prog_environs = ['gnu-azhpc']
    prerun_cmds = [
        'sh aocc-compiler-3.2.0/install.sh',
        'source ./setenv_AOCC.sh'
        ]
    executable = 'clang ./stream.c -o ./stream -fopenmp -mcmodel=large -DSTREAM_TYPE=double -DSTREAM_ARRAY_SIZE=260000000 -DNTIMES=100 -ffp-contract=fast -fnt-store -O3 -ffast-math -ffinite-loops'

    flags = variable(dict, value={
         'hbrs_v3': [   '-mavx2',
                        '-arch zen2'
                    ],
        'hbrs_v2':  [   '-mavx2',
                        '-arch zen2'
                    ]
        })

    @run_after('init')
    def inject_dependencies(self):
        self.depends_on('StreamDownloadTest', udeps.fully)

    @require_deps
    def set_sourcedir(self, StreamDownloadTest):
        self.sourcesdir = os.path.join(
            StreamDownloadTest(part='default', environ='gnu-azhpc').stagedir,
            ''
        )

    @run_before('run')
    def set_num_compiler_flags(self):
        vm_info = self.current_system.node_data
        vm_series = vm_info['vm_series'] 
        self.executable_opts = self.flags.get(vm_series, [])

    @sanity_function
    def validate_download(self):
        return sn.assert_true(os.path.exists('stream'))

@rfm.simple_test
class StreamDownloadTest(rfm.RunOnlyRegressionTest):
    descr = 'Download stream test'
    valid_systems = ['*:default']
    valid_prog_environs = ['gnu-azhpc']
    executable = 'wget'
    executable_opts = [
        'https://raw.githubusercontent.com/jeffhammond/STREAM/master/stream.c'  # noqa: E501
    ]

    @run_after('init')
    def inject_dependencies(self):
        self.depends_on('AOCCDownloadTest', udeps.fully)

    @require_deps
    def set_sourcedir(self, AOCCDownloadTest):
        self.sourcesdir = os.path.join(
            AOCCDownloadTest(part='default', environ='gnu-azhpc').stagedir,
            ''
        )

    @sanity_function
    def validate_download(self):
        return sn.assert_true(os.path.exists('stream.c'))

# rfmdocstart: aoccdownload
@rfm.simple_test
class AOCCDownloadTest(rfm.RunOnlyRegressionTest):
    descr = 'Download AOCC compiler'
    valid_systems = ['*:default']
    valid_prog_environs = ['gnu-azhpc']
    executable = 'wget'
    executable_opts = [
        'https://developer.amd.com/wordpress/media/files/aocc-compiler-3.2.0.tar'  # noqa: E501
    ]
    postrun_cmds = [
        'tar -xf aocc-compiler-3.2.0.tar'
    ]


    @sanity_function
    def validate_download(self):
        return sn.assert_true(os.path.exists('aocc-compiler-3.2.0.tar'))
# rfmdocend: osudownload
