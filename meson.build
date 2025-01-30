project(
    'aaclient', 'cpp', 'cython',
    license: 'BSD-3',
    meson_version: '>= 1.0.1',
    default_options: [
        'cpp_std=c++11',
    ],
)

py = import('python').find_installation()

numpy_inc = run_command(
    py,
    ['-c', 'import numpy; print(numpy.get_include())'],
    check: true,
).stdout().strip()
numpy = declare_dependency(
    include_directories: [numpy_inc],
    compile_args: ['-DNPY_NO_DEPRECATED_API=NPY_1_7_API_VERSION', '-DNPY_TARGET_VERSION=NPY_1_7_API_VERSION'],
)

protobuf_lite = dependency('protobuf-lite', version: '>=2.5.0')
protoc = find_program('protoc')

run_protoc = generator(
    protoc,
    output: ['@BASENAME@.pb.cc', '@BASENAME@.pb.h'],
    arguments: ['--proto_path=@CURRENT_SOURCE_DIR@', '--cpp_out=@BUILD_DIR@', '@INPUT@'],
)

EPICSEvent = run_protoc.process(
    'aaclient/EPICSEvent.proto',
    preserve_path_from : meson.current_source_dir(), # keep aaclient/
)

py.extension_module(
    '_ext',
    'aaclient/ext.pyx',
    EPICSEvent,
    subdir: 'aaclient',
    dependencies: [protobuf_lite, numpy],
    install: true,
    include_directories: ['aaclient'],
    override_options: ['cython_language=cpp'],
)

py.install_sources(
    'aaclient/appl.py',
    'aaclient/conf.py',
    'aaclient/date.py',
    'aaclient/dtype.py',
    'aaclient/__init__.py',
    'aaclient/threading.py',
    'aaclient/util.py',
    pure: false,
    subdir: 'aaclient',
)
py.install_sources(
    'aaclient/test/__init__.py',
    'aaclient/test/test_aa.py',
    'aaclient/test/test_conf.py',
    'aaclient/test/test_date.py',
    'aaclient/test/test_ext.py',
    'aaclient/test/test_RH.pb',
    'aaclient/test/test_threading.py',
    'aaclient/test/test_util.py',
    'aaclient/test/testdata.pb',
    pure: false,
    subdir: 'aaclient/test',
)

