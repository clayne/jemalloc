#!/usr/bin/env python3

from itertools import combinations

travis_template = """\
language: generic
dist: focal

matrix:
  include:
%s

before_script:
  - autoconf
  - scripts/gen_travis.py > travis_script && diff .travis.yml travis_script
  - ./configure ${COMPILER_FLAGS:+ \
      CC="$CC $COMPILER_FLAGS" \
      CXX="$CXX $COMPILER_FLAGS" } \
      $CONFIGURE_FLAGS
  - make -j3
  - make -j3 tests

script:
  - make check
"""

# The 'default' configuration is gcc, on linux, with no compiler or configure
# flags.  We also test with clang, -m32, --enable-debug, --enable-prof,
# --disable-stats, and --with-malloc-conf=tcache:false.  To avoid abusing
# travis though, we don't test all 2**7 = 128 possible combinations of these;
# instead, we only test combinations of up to 2 'unusual' settings, under the
# hope that bugs involving interactions of such settings are rare.
MAX_UNUSUAL_OPTIONS = 2

os_default = 'linux'
os_unusual = 'osx'

arch_default = 'amd64'
arch_unusual = 'ppc64le'

compilers_default = 'CC=gcc CXX=g++'
compilers_unusual = 'CC=clang CXX=clang++'

compiler_flag_unusuals = ['-m32']

configure_flag_unusuals = [
    '--enable-debug',
    '--enable-prof',
    '--disable-stats',
    '--disable-libdl',
    '--enable-opt-safety-checks',
    '--with-lg-page=16',
]

malloc_conf_unusuals = [
    'tcache:false',
    'dss:primary',
    'percpu_arena:percpu',
    'background_thread:true',
]

all_unusuals = (
    [os_unusual] + [arch_unusual] + [compilers_unusual] + compiler_flag_unusuals
    + configure_flag_unusuals + malloc_conf_unusuals
)

unusual_combinations_to_test = []
for i in range(MAX_UNUSUAL_OPTIONS + 1):
    unusual_combinations_to_test += combinations(all_unusuals, i)

gcc_multilib_set = False
gcc_ppc_set = False
# Formats a job from a combination of flags
def format_job(combination):
    global gcc_multilib_set
    global gcc_ppc_set

    os = os_unusual if os_unusual in combination else os_default
    compilers = compilers_unusual if compilers_unusual in combination else compilers_default
    arch = arch_unusual if arch_unusual in combination else arch_default
    compiler_flags = [x for x in combination if x in compiler_flag_unusuals]
    configure_flags = [x for x in combination if x in configure_flag_unusuals]
    malloc_conf = [x for x in combination if x in malloc_conf_unusuals]

    # Filter out unsupported configurations on OS X.
    if os == 'osx' and ('dss:primary' in malloc_conf or \
      'percpu_arena:percpu' in malloc_conf or 'background_thread:true' \
      in malloc_conf):
        return ""
    # gcc is just a redirect to clang on OS X. No need to test both.
    if os == 'osx' and compilers_unusual in combination:
        return ""
    if len(malloc_conf) > 0:
        configure_flags.append('--with-malloc-conf=' + ",".join(malloc_conf))

    # Filter out an unsupported configuration - heap profiling on OS X.
    if os == 'osx' and '--enable-prof' in configure_flags:
        return ""

    # Filter out unsupported OSX configuration on PPC64LE
    if arch == 'ppc64le' and (
        os == 'osx'
        or '-m32' in combination
        or compilers_unusual in combination
        ):
        return ""

    job = ""
    job += '    - os: %s\n' % os
    job += '      arch: %s\n' % arch

    if '-m32' in combination and os == 'linux':
        job += '      addons:'
        if gcc_multilib_set:
            job += ' *gcc_multilib\n'
        else:
            job += ' &gcc_multilib\n'
            job += '        apt:\n'
            job += '          packages:\n'
            job += '            - gcc-multilib\n'
            job += '            - g++-multilib\n'
            gcc_multilib_set = True

    # We get some spurious errors when -Warray-bounds is enabled.
    extra_cflags = ['-Werror', '-Wno-array-bounds']
    if 'clang' in compilers or os == 'osx':
        extra_cflags += [
	    '-Wno-unknown-warning-option',
	    '-Wno-ignored-attributes'
	]
    if os == 'osx':
        extra_cflags += [
	    '-Wno-deprecated-declarations',
	]
    env_string = ('{} COMPILER_FLAGS="{}" CONFIGURE_FLAGS="{}" '
        'EXTRA_CFLAGS="{}"'.format(
        compilers, ' '.join(compiler_flags), ' '.join(configure_flags),
        ' '.join(extra_cflags)))

    job += '      env: %s\n' % env_string
    return job

include_rows = ""
for combination in unusual_combinations_to_test:
    include_rows += format_job(combination)

# Development build
include_rows += '''\
    # Development build
    - os: linux
      env: CC=gcc CXX=g++ COMPILER_FLAGS="" CONFIGURE_FLAGS="--enable-debug --disable-cache-oblivious --enable-stats --enable-log --enable-prof" EXTRA_CFLAGS="-Werror -Wno-array-bounds"
'''

# Enable-expermental-smallocx
include_rows += '''\
    # --enable-expermental-smallocx:
    - os: linux
      env: CC=gcc CXX=g++ COMPILER_FLAGS="" CONFIGURE_FLAGS="--enable-debug --enable-experimental-smallocx --enable-stats --enable-prof" EXTRA_CFLAGS="-Werror -Wno-array-bounds"
'''

# Does not seem to be working on newer travis machines. Valgrind has long been a
# pain point; abandon it for now.
# Valgrind build bots
#include_rows += '''
#    # Valgrind
#    - os: linux
#      arch: amd64
#      env: CC=gcc CXX=g++ COMPILER_FLAGS="" CONFIGURE_FLAGS="" EXTRA_CFLAGS="-Werror -Wno-array-bounds" JEMALLOC_TEST_PREFIX="valgrind"
#      addons:
#        apt:
#          packages:
#            - valgrind
#'''

# To enable valgrind on macosx add:
#
#  - os: osx
#    env: CC=gcc CXX=g++ COMPILER_FLAGS="" CONFIGURE_FLAGS="" EXTRA_CFLAGS="-Werror -Wno-array-bounds" JEMALLOC_TEST_PREFIX="valgrind"
#    install: brew install valgrind
#
# It currently fails due to: https://github.com/jemalloc/jemalloc/issues/1274

print(travis_template % include_rows)
