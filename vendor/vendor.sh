if echo $PACKAGES |grep -q panda3d
then
    echo $PACKAGES
else
    export PACKAGES="emsdk hpy panda3d"
    export STATIC=true
fi
export VENDOR=panda3d
export LD_VENDOR="-sUSE_WEBGL2 -sFULL_ES2 -sFULL_ES3"
