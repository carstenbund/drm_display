import numpy as np


class FBDisplay(object):
    def __init__(self, display="/dev/fb0", width=None, height=None):
        # width/height are accepted for API compatibility with DRMDisplay but
        # ignored — actual size is always read from the framebuffer device.
        self.display = display
        self.screen_width, self.screen_height = self.get_screen_size(display)
        self.fb = self.setup_display(display)

    def get_screen_size(self, display, size=(1920, 1080)):
        try:
            display = display[5:]
            #print(display)
            fb_name = '/sys/class/graphics/' + display + '/virtual_size'
            #print(fb_name)
            with open(fb_name, 'r') as file:
                screen = file.read().strip().split(',')
                #print(f"Screen size reported: ${screen}")
        except:
            screen = size
        width, height = screen
        return int(width), int(height)

    def setup_display(self, display=None):
        if display is not None:
            try:
                print(f"Set up display: {display}")
                fb = np.memmap(display, dtype='uint8', mode='w+', shape=(self.screen_height, self.screen_width, 4))
            except:
                fb = np.zeros((self.screen_height, self.screen_width, 4), dtype='uint8')
        else:
            fb = np.zeros((self.screen_height, self.screen_width, 4), dtype='uint8')

        print(fb.shape)
        return fb

    def clear(self):
        self.fb[:] = 0

    def send_full_image(self, canvas):
        self.fb[:canvas.shape[0], :canvas.shape[1], :4] = canvas
    
    def close(self):
        return
        self.clear()
        self.fb = None

# Example main function for testing purposes
if __name__ == "__main__":
    display = FBDisplay("/dev/fb0")
    try:
        # Example: fill the screen with a specific color
        blue =np.arange(display.screen_height*display.screen_width*4, dtype='uint8').reshape(display.screen_height,display.screen_width,4)
        blue[:] = [255,8,8,0]
        display.send_full_image(blue)
        pass
    finally:
        display.close()

