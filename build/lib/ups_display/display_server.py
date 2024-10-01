import threading
import time
import os
import urllib

import Adafruit_SSD1306
import PIL.Image
import PIL.ImageFont
import PIL.ImageDraw

import socketserver

from http import server

from ups_display import ina219

from .utils import ip_address, power_mode, power_usage, cpu_usage, gpu_usage, memory_usage, disk_usage


class WebServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True
pass # WebServer

class DisplayServer():
    
    def __init__( self ):
        print( "Initing display server ..." , flush=1 )

        adress = os.popen("i2cdetect -y -r 1 0x42 0x42 | egrep '42' | awk '{print $2}'").read()
        if(adress=='42\n'):
            self.ina = ina219.INA219(addr=0x42)
        else:
            self.ina = None
        pass

        display = Adafruit_SSD1306.SSD1306_128_32(rst=None, i2c_bus=1, gpio=1) 

        self.display = display

        print( f"display width = {display.width}, height = {display.height}", flush=1 )

        self.display.begin()
        self.display.clear()
        self.display.display()
        
        self.font = PIL.ImageFont.load_default()
        self.image = PIL.Image.new('1', (self.display.width, self.display.height))
        self.draw = PIL.ImageDraw.Draw(self.image)
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=255)

        self.display.image(self.image)
        self.display.display()
        
        self.stats_enabled = False
        self.stats_thread = None
        self.stats_interval = 2.5
        self.enable_stats()

        print( "Done initing display server" , flush=1 )
    pass
        
    def run_display_stats(self):
        Charge = False

        idx = 0 
        p = 0 
        while self.stats_enabled :
            idx += 1

            w = self.image.width
            h = self.image.height

            top = 0
            line_no = -1

            self.draw.rectangle((0, 0, w, h), outline=0, fill=0)
            self.draw.rectangle((0, 0, w -1, h -1), outline=255, fill=0)

            if idx%2 == 0 : 
                # power state
                line_no += 1
                top = ( 2 + (h-2)/2*line_no )

                power_mode_str = power_mode()

                if(self.ina != None):
                    bus_voltage = self.ina.getBusVoltage_V()        # voltage on V- (load side)
                    current = self.ina.getCurrent_mA()                # current in mA
                    p = (bus_voltage - 6)/2.4*100
                    if(p > 100):p = 100
                    if(p < 0):p = 0
                    if(current > 30):
                        Charge = not Charge
                    else:
                        Charge = False

                    charge_state = "*" if Charge else "-"

                    # power_mode_str + (" %.1fV")%bus_voltage + (" %.2fA")%(current/1000) + (" %2.0f%%")%p
                    text = f"{charge_state} {power_mode_str} {bus_voltage:.1f}V {current/1000:.2f}A"
                    self.draw.text((4, top), text, font=self.font, fill=255)
                else:
                    self.draw.text((4, top), 'MODE: ' + power_mode_str, font=self.font, fill=255)
                pass
            
                # show IP address
                line_no += 1
                top = ( 2 + (h-2)/2*line_no )

            
                if ip_address('eth0') is not None:
                    self.draw.text((4, top), '- IP: ' + str(ip_address('eth0')), font=self.font, fill=255)
                elif ip_address('wlan0') is not None:
                    self.draw.text((4, top), '- IP: ' + str(ip_address('wlan0')), font=self.font, fill=255)
                else:
                    self.draw.text((4, top), '- IP: not available')
                pass 
            else :  
                # set IP address
                line_no += 1
                top = ( 2 + (h-2)/2*line_no )

                offset = 3 * 8
                headers = ['PWR', 'CPU', 'GPU', 'RAM', 'DSK']

                text = " ".join( headers )
                self.draw.text((4, top), text, font=self.font, fill=255) 

                # set stats fields
                line_no += 1
                top = ( 2 + (h-2)/2*line_no )

                power_watts  = '%.1f' % p
                gpu_percent  = '%02d%%' % int(round(gpu_usage() * 100.0, 1))
                cpu_percent  = '%02d%%' % int(round(cpu_usage() * 100.0, 1))
                ram_percent  = '%02d%%' % int(round(memory_usage() * 100.0, 1))
                disk_percent = '%02d%%' % int(round(disk_usage() * 100.0, 1))
                
                entries = [power_watts, cpu_percent, gpu_percent, ram_percent, disk_percent]

                text = " ".join( entries )
                self.draw.text((4, top), text, font=self.font, fill=255)  
            pass

            self.display.image( self.image )
            self.display.display()

            if 0 : print( f"idx = {idx}", flush=1 )
    
            time.sleep(self.stats_interval)
        pass
    pass
            
    def enable_stats(self):
        # start stats display thread
        if not self.stats_enabled:
            self.stats_enabled = True
            self.stats_thread = threading.Thread(target=self.run_display_stats)
            self.stats_thread.start()
        pass
    pass
        
    def disable_stats(self):
        self.stats_enabled = False
        if self.stats_thread is not None:
            self.stats_thread.join()
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
        self.display.image(self.image)
        self.display.display()
    pass

    def set_text(self, text):
        self.disable_stats()
        self.draw.rectangle((0, 0, self.image.width, self.image.height), outline=0, fill=0)
        
        lines = text.split('\n')
        top = 2
        for line in lines:
            self.draw.text((4, top), line, font=self.font, fill=255)
            top += 10
        
        self.display.image(self.image)
        self.display.display()
    pass
pass # DisplayServer

class WebHandler(server.BaseHTTPRequestHandler):

    displayServer = DisplayServer()

    def do_GET(self):
        if self.displayServer is None :
            self.displayServer = DisplayServer()
        pass

        if self.path == '/stats/on':
            self.displayServer.enable_stats()
            return "stats enabled"
        elif self.path == '/stats/off':
            self.displayServer.disable_stats()
            return "stats disabled"
        elif '/text/' in self.path :
            params = urllib.parse.parse_qs( self.path )
            
            text = ""
            
            if "text" in params :
                text = params[ "text" ][0]
            pass

            self.displayServer.set_text( text )
            return f'set text: \n\n{text}'
        else :
            return f"invalid url: {self.path}"
        pass
    pass

pass # WebHandler

if __name__ == '__main__':
    print( f"ups display server v1.0.01", flush=1 )

    if 0 :
        pass
    elif 1 :
        address = ('', 8000)
        server = WebServer( address, WebHandler )
        server.serve_forever()
    pass

pass

