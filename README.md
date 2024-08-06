## drm_player


frambuffer setup in C in drm_display.c
compile with:
```
gcc -shared -o libdrm_display.so -I/usr/include/libdrm -fPIC drm_display.c -ldrm
```

python bindings in drm_display.py

to use
 
```
import DRMdisplay
```

initialize a display

```
display = DRMDisplay('/dev/dri/card0')
```


```
display.send_full_image(img)
```
