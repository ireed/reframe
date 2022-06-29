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

class HPLBenchmarkTestBase(rfm.RunOnlyRegressionTest):
    '''Base class of HPL benchmark runtime tests'''

    valid_systems = ['*']
    valid_prog_environs = ['*']
    sourcesdir = None
    prerun_cmds = ['. /etc/profile.d/modules.sh']
    
    # rfmdocstart: set_deps
    @run_after('init')
    def set_dependencies(self):
        self.depends_on('HPLBuildTest', udeps.by_env)
    # rfmdocend: set_deps

@rfm.simple_test
class HPLSingleVMTest(HPLBenchmarkTestBase):
    descr = 'HPL Single VM test using pssh'
    num_tasks = 0
    
    @require_deps
    def set_sourcedir(self, HPLBuildTest):
        stage_path = os.path.join(
            HPLBuildTest(part='default', environ='gnu-azhpc').stagedir,
            ''
        )
        repo_path = stage_path.replace("stage","repo")
        self.sourcesdir = repo_path
  
    @run_after('init')
    def set_hpl_prerun_options(self):
        vm_info = self.current_system.node_data
        vm_series = vm_info['vm_series']
        self.prerun_cmds = [
            'echo $(hostname)',
            'mkdir HPL-$(hostname)',
            'cd HPL-$(hostname)',
            'echo $(hostname) > hosts.txt',
            'cp ../HPL.dat .',
            'cp ../appfile*_ccx .',
            'cp ../xhpl_ccx.sh .',
            'cp ../xhpl .',
            'echo always | sudo tee /sys/kernel/mm/transparent_hugepage/enabled',
            'echo always | sudo tee /sys/kernel/mm/transparent_hugepage/defrag'
            ]
        if vm_series == 'hbrs_v2':
            self.prerun_cmds.append('sed -i "s/4           Ps/6           Ps/g" HPL.dat')
            self.prerun_cmds.append('sed -i "s/4            Qs/5            Qs/g" HPL.dat')

    executable = 'mpirun'
    cmda = "echo "
    cmdb = "system: $(hostname) HPL: $(grep WR hpl*.log | awk -F ' ' '{print $7}')"
    cmdc = "  >> ../hpl-test-results.log"
    cmd = cmda+cmdb+cmdc
    postrun_cmds = [
        'cat hpl*.log',
        cmd,
        'cp hosts.txt ../',
        'cd ../',
        'cat hpl-test-results.log',
    ]

    @run_before('run')
    def set_hpl_options(self):
        vm_info = self.current_system.node_data
        vm_series = vm_info['vm_series']
        if vm_series == 'hbrs_v3':
            self.executable_opts = [
                '--mca mpi_leave_pinned 1',
                '--bind-to none',
                '--report-bindings',
                '--mca btl self,vader',
                '--map-by ppr:1:l3cache',
                '-x OMP_NUM_THREADS=6',
                '-x OMP_PROC_BIND=TRUE',
                '-x OMP_PLACES=cores',
                '-x LD_LIBRARY_PATH',
                '-app ./appfile_ccx  >> hpl-$(hostname).log'
            ]
        elif vm_series == 'hbrs_v2':
            self.executable_opts = [
                '-np 30',
                '--report-bindings',
                '--mca btl self,vader',
                '--map-by ppr:1:l3cache:pe=4',
                '-x OMP_NUM_THREADS=4',
                '-x OMP_PROC_BIND=TRUE',
                '-x OMP_PLACES=cores',
                '-x LD_LIBRARY_PATH',
                './xhpl >> hpl-$(hostname).log'
            ]

    @sanity_function
    def assert_num_messages(self):
        num_tests = sn.len(sn.findall(r'HPL: (\S+)',
                                         self.stagedir+'/hpl-test-results.log'))
        num_nodes = sum(1 for _ in open(self.stagedir+'/hosts.txt'))
        return sn.assert_eq(num_tests, num_nodes)

    @performance_function('Gflops')
    def extract_hpl_s(self, vm='c5e'):
         return sn.extractsingle(rf'system: {vm} HPL: (\S+)',self.stagedir+'/hpl-test-results.log', 1, float)


    @run_before('performance')
    def set_perf_variables(self):
        
        self.perf_variables = {}
        with open(self.stagedir+'/hpl-test-results.log',"r") as f:
            sys_names = f.read()

        systems = re.findall(r"system:\s(\S+)\s+.*",sys_names,re.M)
        hpl = re.findall(r"HPL: (\S+)",sys_names,re.M)

        vm_info = self.current_system.node_data
        vm_series = vm_info['vm_series']
        temp = {vm_series: {}}

        if vm_info != None and 'nhc_values' in vm_info:
            for i in systems:
                temp[vm_series][i] = (vm_info['nhc_values']['hpl_performance'], 
                                        vm_info['nhc_values']['hpl_performance_limits'][0],
                                        vm_info['nhc_values']['hpl_performance_limits'][1],
                                        'Gflops')

        self.reference = temp

        for i in systems:
            self.perf_variables[i] = self.extract_hpl_s(i)

        results = {}
        for i in range(len(systems)):
            results[systems[i]] = hpl[i]

        with open(self.outputdir+"/hpl_test_results.json", "w") as outfile:
            js.dump(results, outfile, indent=4)


@rfm.simple_test
class HPLBuildTest(rfm.RunOnlyRegressionTest):
    descr = 'HPL benchmark build test'
    valid_systems = ['*']
    valid_prog_environs = ['*']
    executable = './hpl_build_script.sh'
    prerun_cmds = ['. /etc/profile.d/modules.sh']

    @run_after('init')
    def inject_dependencies(self):
        self.depends_on('HPLDownloadTest', udeps.fully)

    @require_deps
    def set_sourcedir(self, HPLDownloadTest):
        stage_path = os.path.join(
            HPLDownloadTest(part='default', environ='gnu-azhpc').stagedir,
            ''
        )
        repo_path = stage_path.replace("stage","repo")
        self.sourcesdir = repo_path

    @run_before('run')
    def check_if_already_exists(self):
        stage_path = self.stagedir
        repo_path = stage_path.replace("stage","repo")
        if os.path.exists(repo_path) and os.path.exists(f"{repo_path}/xhpl"):
            os.system(f"cp -r {repo_path}/* {stage_path}/")
            self.executable = 'echo'
            self.executable_opts = [
                'already ran'  # noqa: E501
            ]
            self.postrun_cmds = [
                'rm -rf blis/.git'
            ]

    @run_after('run')
    def copy_to_repo(self):
        stage_path = self.stagedir
        repo_path = stage_path.replace("stage","repo")
        os.system(f"mkdir -p {repo_path}") 
        os.system(f"cp -r {stage_path}/* {repo_path}/") 

    @sanity_function
    def validate_download(self):
        return sn.assert_true(os.path.exists('xhpl'))

@rfm.simple_test
class HPLDownloadTest(rfm.RunOnlyRegressionTest):
    descr = 'HPL benchmarks download sources'
    valid_systems = ['*']
    valid_prog_environs = ['*']
    executable = 'wget'
    prerun_cmds = ['. /etc/profile.d/modules.sh']
    executable_opts = [
        'https://raw.githubusercontent.com/arstgr/hpl/main/hpl_build_script.sh'  # noqa: E501
    ]
    postrun_cmds = [
        'chmod +x hpl_build_script.sh'
    ]

    @run_before('run')
    def check_if_already_exists(self):
        stage_path = self.stagedir
        repo_path = stage_path.replace("stage","repo")
        if os.path.exists(repo_path) and os.path.exists(f"{repo_path}/hpl_build_script.sh"):
            self.executable = 'echo'
            self.executable_opts = [
                'already ran'  # noqa: E501
            ]
            self.postrun_cmds = [
                'chmod +x hpl_build_script.sh'
            ]
            
    @run_after('run')
    def copy_to_repo(self):
        stage_path = self.stagedir
        repo_path = stage_path.replace("stage","repo")
        os.system(f"mkdir -p {repo_path}") 
        os.system(f"cp -r {stage_path}/* {repo_path}/") 

    @sanity_function
    def validate_download(self):
        stage_path = self.stagedir
        repo_path = stage_path.replace("stage","repo")
        return sn.assert_true(os.path.exists(f"{repo_path}/hpl_build_script.sh"))
