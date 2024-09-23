#!/bin/bash

export SDKROOT=${SDKROOT:-/opt/python-wasm-sdk}
export CONFIG=${CONFIG:-$SDKROOT/config}

#   --override STDFLOAT_DOUBLE=1


. ${CONFIG}

echo "

    * building Panda3D for ${CIVER}, PYBUILD=$PYBUILD => CPython${PYMAJOR}.${PYMINOR}
            PYBUILD=$PYBUILD
            EMFLAVOUR=$EMFLAVOUR
            SDKROOT=$SDKROOT
            SYS_PYTHON=${SYS_PYTHON}

" 1>&2

outputdir=$(pwd)/build/panda3d





# fix some free threading detection problems.
if echo $PYBUILD|grep 3.13
then
    [ -L $PREFIX/include/python3.13t ]  || ln -s $PREFIX/include/python3.13 $PREFIX/include/python3.13t
    [ -L $PREFIX/lib/libpython3.13t.a ] || ln -s $PREFIX/lib/libpython3.13.a $PREFIX/lib/libpython3.13t.a
    export IGATE_WHEEL=$(realpath packages.d/panda3d/panda3d_interrogate-0.2.0-cp313-cp313t-linux_x86_64.whl)
fi

export PYLINK="\
 ${SDKROOT}/prebuilt/emsdk/libHacl_Hash_SHA2${PYBUILD}.a \
 ${SDKROOT}/prebuilt/emsdk/libexpat${PYBUILD}.a \
 ${SDKROOT}/prebuilt/emsdk/libmpdec${PYBUILD}.a \
 ${SDKROOT}/devices/emsdk/usr/lib/libssl.a \
 ${SDKROOT}/devices/emsdk/usr/lib/libcrypto.a \
 -lffi"


pushd $(pwd)/external

if true
then

    if [ -d panda3d ]
    then
        pushd $(pwd)/panda3d
        git restore .
        git pull

    else
        git clone --no-tags --depth 1 --single-branch --branch webgl-port https://github.com/pmp-p/panda3d panda3d
        pushd $(pwd)/panda3d
        git submodule update --init --recursive
    fi


    [ -f panda3d.static.c ] && rm panda3d.static.c

    if [ -d ${WORKSPACE}/wip/panda3d ]
    then
        cp -vf /data/git/pygbag/wip/panda3d/makepanda*.py makepanda/
        for patch in /data/git/pygbag/wip/panda3d/*.diff
        do
            patch -p1 < $patch
        done
    else
        wget -Omakepanda/makepandacore.upstream.py https://raw.githubusercontent.com/panda3d/panda3d/master/makepanda/makepandacore.py
        wget -Omakepanda/makepanda.upstream.py https://raw.githubusercontent.com/panda3d/panda3d/master/makepanda/makepanda.py
        wget -Omakepanda/makepandacore.py https://raw.githubusercontent.com/pmp-p/panda3d/python-wasm-sdk/makepanda/makepandacore.py
        wget -Omakepanda/makepanda.py https://raw.githubusercontent.com/pmp-p/panda3d/python-wasm-sdk/makepanda/makepanda.py
    fi

    wget -Opanda3d.static.c https://raw.githubusercontent.com/pmp-p/panda3d/python-wasm-sdk/panda3d.static.c



    #wget -O- https://patch-diff.githubusercontent.com/raw/panda3d/panda3d/pull/1684.diff | patch -p1
    #fixed by https://github.com/panda3d/panda3d/commit/c05a63f4ae9bd7d8d7539e79667051e6684a2267 which is :
    patch -p1 <<END
diff --git a/panda/src/pipeline/cycleDataLockedStageReader.I b/panda/src/pipeline/cycleDataLockedStageReader.I
index a471aac0b7..2e2477fb9a 100644
--- a/panda/src/pipeline/cycleDataLockedStageReader.I
+++ b/panda/src/pipeline/cycleDataLockedStageReader.I
@@ -180,7 +180,7 @@ CycleDataLockedStageReader(const CycleDataLockedStageReader<CycleDataType> &copy
 template<class CycleDataType>
 INLINE CycleDataLockedStageReader<CycleDataType>::
 CycleDataLockedStageReader(CycleDataLockedStageReader<CycleDataType> &&from) noexcept :
-  _pointer(from._cycler)
+  _pointer(from._pointer)
 {
   from._pointer = nullptr;
 }
END


    # merged
    #wget -O- https://patch-diff.githubusercontent.com/raw/panda3d/panda3d/pull/1608.diff | patch -p1

    #wget -O- https://patch-diff.githubusercontent.com/raw/pmp-p/panda3d/pull/4.diff | patch -p1
    #wget -O-  https://patch-diff.githubusercontent.com/raw/pmp-p/panda3d/pull/9.diff | patch -p1

    patch -p1 <<END
diff --git a/panda/src/pgraph/nodePath_ext.cxx b/panda/src/pgraph/nodePath_ext.cxx
index 7995717979..e05877be53 100644
--- a/panda/src/pgraph/nodePath_ext.cxx
+++ b/panda/src/pgraph/nodePath_ext.cxx
@@ -279,7 +279,7 @@ set_shader_inputs(PyObject *args, PyObject *kwargs) {
   PyObject *key, *value;
   Py_ssize_t pos = 0;

-  Py_BEGIN_CRITICAL_SECTION(dict);
+  Py_BEGIN_CRITICAL_SECTION(kwargs);
   while (PyDict_Next(kwargs, &pos, &key, &value)) {
     char *buffer;
     Py_ssize_t length;
END

    patch -p1 <<END
diff --git a/panda/src/pgraph/cullBinManager.cxx b/panda/src/pgraph/cullBinManager.cxx
index cfacd85..92052aa 100644
--- a/panda/src/pgraph/cullBinManager.cxx
+++ b/panda/src/pgraph/cullBinManager.cxx
@@ -210,7 +210,9 @@ make_new_bin(int bin_index, GraphicsStateGuardianBase *gsg,
 void CullBinManager::
 register_bin_type(BinType type, CullBinManager::BinConstructor *constructor) {
   bool inserted = _bin_constructors.insert(BinConstructors::value_type(type, constructor)).second;
+#if !defined(__EMSCRIPTEN__)
   nassertv(inserted);
+#endif
 }

 /**
END

#patch -p1 <<END
#diff --git a/makepanda/makepandacore.py b/makepanda/makepandacore.py
#index 02c11be..11388f2 100644
#--- a/makepanda/makepandacore.py
#+++ b/makepanda/makepandacore.py
#@@ -1414,7 +1414,7 @@ def GetThirdpartyDir():
#         THIRDPARTYDIR = base + "/android-libs-%s/" % (target_arch)

#     elif (target == 'emscripten'):
#-        THIRDPARTYDIR = base + "/emscripten-libs/"
#+        THIRDPARTYDIR = base + "/lib/"

#     else:
#         Warn("Unsupported platform:", target)
#END

    patch -p1 <<END
diff --git a/panda/src/express/virtualFileSystem.cxx b/panda/src/express/virtualFileSystem.cxx
index 37c220f..961245e 100644
--- a/panda/src/express/virtualFileSystem.cxx
+++ b/panda/src/express/virtualFileSystem.cxx
@@ -28,7 +28,7 @@
 #include "executionEnvironment.h"
 #include "pset.h"

-#ifdef __EMSCRIPTEN__
+#if 0
 #include "virtualFileMountHTTP.h"
 #endif

@@ -857,7 +857,7 @@ get_global_ptr() {
     _global_ptr = new VirtualFileSystem;

     // Set up the default mounts.  First, there is always the root mount.
-#ifdef __EMSCRIPTEN__
+#if 0
     // Unless we're running in node.js, we don't have a filesystem, and instead
     // mount the current server root as our filesystem root.
     bool is_node = (bool)EM_ASM_INT(return (typeof process === 'object' && typeof process.versions === 'object' && typeof process.versions.node === 'string'));
END


    patch -p1 <<END
diff --git a/direct/src/showbase/Loader.py b/direct/src/showbase/Loader.py
index 92ed0cf..a3c9348 100644
--- a/direct/src/showbase/Loader.py
+++ b/direct/src/showbase/Loader.py
@@ -26,7 +26,7 @@ from panda3d.core import Loader as PandaLoader
 from direct.directnotify.DirectNotifyGlobal import directNotify
 from direct.showbase.DirectObject import DirectObject
 import warnings
-
+import sys
 # You can specify a phaseChecker callback to check
 # a modelPath to see if it is being loaded in the correct
 # phase
@@ -952,7 +952,14 @@ class Loader(DirectObject):

         # showbase-created sfxManager should always be at front of list
         if self.base.sfxManagerList:
-            return self.loadSound(self.base.sfxManagerList[0], *args, **kw)
+            __WASM__ = sys.platform in ('emscripten','wasi')
+            fixargs = []
+            for arg in map(str, args):
+                if __WASM__ and (arg.endswith('.wav') or arg.endswith('.mp3')):
+                    fixargs.append(arg[:-3]+'ogg')
+                else:
+                    fixargs.append(arg)
+            return self.loadSound(self.base.sfxManagerList[0], *fixargs, **kw)
         return None

     def loadMusic(self, *args, **kw):
END


    export P3D_SRC_DIR=$(pwd)
    popd

else
    pushd $(pwd)/panda3d
    export P3D_SRC_DIR=$(pwd)
fi

popd


mkdir -p ${outputdir}

pushd ${outputdir}

if which cmake
then
    echo "
    * using local cmake
" 1>&2
else
    $SYS_PYTHON -m pip install cmake
fi


. ${SDKROOT}/emsdk/emsdk_env.sh
export EMSDK_PYTHON=$SYS_PYTHON
export CC=emcc
export CXX=em++


if false
then
    emcmake cmake $P3D_SRC_DIR \
     -DCMAKE_INSTALL_PREFIX=$PREFIX \
        -DHAVE_EGG=YES -DHAVE_SSE2=NO -DHAVE_THREADS=NO \
        -DHAVE_OPENAL=Yes -DHAVE_OPENSSL=NO \
-DHAVE_EGL=NO -DHAVE_GL=NO -DHAVE_GLX=NO -DHAVE_X11=NO -DHAVE_GLES1=NO -DHAVE_GLES2=YES \
        -DHAVE_PYTHON=YES \
        -DPYMAJOR=$PYMAJOR -DPYMINOR=$PYMINOR -DPython_DIR=${PREFIX} \
        -DPython3_EXECUTABLE:FILEPATH=${SDKROOT}/python3-wasm \
        -DPython3_INCLUDE_DIR=${PREFIX}/include/python${PYBUILD} \
        -DPython3_LIBRARY=${PREFIX}/lib \
        -DPython3_FOUND=TRUE \
        -DPython3_Development_FOUND=TRUE \
        -DPython3_Development.Module_FOUND=TRUE \
        -DPython3_Development.Embed_FOUND=TRUE \

else
    pushd $P3D_SRC_DIR

#    mkdir -p $outputdir/bin

#    echo '#!/bin/bash
#    node $0.js $@
#    ' > $outputdir/bin/interrogate

#    ln $outputdir/bin/interrogate $outputdir/bin/interrogate_module
#    chmod +x $outputdir/bin/*

    #export PATH=$outputdir/bin:$PATH

# assimp : NOT OK
MAKEPANDA_THIRDPARTY=$SDKROOT/devices/emsdk/usr /opt/python-wasm-sdk/python3-wasm makepanda/makepanda.py \
    --static --nothing \
    --use-egg --use-direct --use-pandafx \
    --optimize 3 \
    --no-x11 --no-egl --no-gles --use-gles2 \
    --use-vorbis --use-freetype --use-harfbuzz \
    --use-zlib --use-png --use-jpeg \
    \
    --use-openal --use-pandaphysics --use-pandaparticlesystem \
    \
    --use-ode \
     --bullet-incdir=$PREFIX/ode \
     --bullet-libdir=$PREFIX/lib \
    \
    --use-bullet \
     --bullet-incdir=$PREFIX/include/bullet \
     --bullet-libdir=$PREFIX/lib \
    \
     --use-assimp \
     --assimp-incdir=$PREFIX/include/assimp \
     --assimp-libdir=$PREFIX/lib \
    \
     --use-python \
     --python-incdir=$PREFIX/include \
     --python-libdir=$PREFIX/lib \
    \
     --no-openssl --no-sse2 --no-neon \
     --no-ffmpeg --no-tiff --no-eigen \
     --override HAVE_THREADS=UNDEF --verbose --wheel --static \
     --outputdir $outputdir \
 | grep --line-buffered -v ^Adding | grep --line-buffered -v ^Ignoring

    rm ${SDKROOT}/prebuilt/emsdk/libpanda3d${PYBUILD}.a $outputdir/lib/libstatic.a $outputdir/lib/libstatic.o
fi

# TODO :
# init_libOpenALAudio();
# init_libpandaegg();
# init_libpnmimagetypes();
# init_libmovies();


EMPIC=${SDKROOT}/emsdk/upstream/emscripten/cache/sysroot/lib/wasm32-emscripten/pic

TAG=${PYMAJOR}${PYMINOR}

if emcc -fPIC -I$SDKROOT/devices/emsdk/usr/include/python${PYBUILD} -c -o $outputdir/lib/libstatic.o panda3d.static.c
then
    if $SDKROOT/emsdk/upstream/emscripten/emar rcs $outputdir/lib/libstatic.a $outputdir/lib/libstatic.o
    then
        LINKALL=$(find $outputdir/lib|grep \\.a$)
        emcc -r -Wl,--whole-archive -o $outputdir/libpanda3d${PYBUILD}.o $LINKALL
        emar cr ${SDKROOT}/prebuilt/emsdk/libpanda3d${PYBUILD}.a $outputdir/libpanda3d${PYBUILD}.o

        emcc -O0 -g0 -shared \
         -o $outputdir/lib/static.cpython-${TAG}-wasm32-emscripten.so \
         ${SDKROOT}/prebuilt/emsdk/libpanda3d${PYBUILD}.a \
         $EMPIC/libfreetype.a $EMPIC/libharfbuzz.a $EMPIC/libvorbis.a $EMPIC/libogg.a \
             /opt/python-wasm-sdk/devices/emsdk/usr/lib/libBullet*.a \
            /opt/python-wasm-sdk/devices/emsdk/usr/lib/libode.a \
            -lpng

        TARGET_FOLDER=testing/panda3d-1.11.0-cp${TAG}-cp${TAG}-wasm32_${WASM_FLAVOUR}_emscripten
        mkdir -p ${TARGET_FOLDER}

        pushd ${TARGET_FOLDER}
        unzip -qo ../../panda3d-1.11.0-cp${TAG}-cp${TAG}-wasm32_${WASM_FLAVOUR}_emscripten.whl
        [ -d deploy_libs ] && rm -rf deploy_libs
        [ -d build ] && rm -rf build


        echo "import panda3d.static" >> panda3d/__init__.py
        mv ../../../../build/panda3d/lib/static.cpython-${TAG}-wasm32-emscripten.so panda3d/
        echo "panda3d/__init__.py,," > ../RECORD
        echo "panda3d/static.cpython-${TAG}-wasm32-emscripten.so,," >> ../RECORD
        grep -v ^deploy_libs panda3d-*.dist-info/RECORD |grep -v ^panda3d/__init__.py >> ../RECORD
        mv ../RECORD panda3d-*.dist-info/RECORD

        if [ -d /data/git/archives/repo/pkg ]
        then
            PYGBAG_VERSION=$(PYTHONPATH=${WORKSPACE}/src $SYS_PYTHON -c "print(__import__('pygbag').VERSION)")
            whl=/data/git/archives/repo/cp${PYMAJOR}${PYMINOR}-${PYGBAG_VERSION}/$(basename $(pwd)).whl
            [ -f $whl ] && rm $whl
            [ -f main.py ] && rm main.py $(find -type f|grep .-pygbag\\..)
            zip $whl -r .
            touch main.py
        fi
        popd
    else
        echo "error building loader module library"
        exit 248
    fi
else
    echo "error building loader object"
    exit 246
fi



