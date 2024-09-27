import numpy as np
import pandas as pd
import matplotlib
import pymmcore
from IPython.display import clear_output
from time import sleep
import matplotlib.pyplot as plt
import time
import xml.etree.ElementTree as ET
import h5py

def load_multipoints(multipoints_path,filetype="auto"):
    if filetype=="auto":
        file_suffix = multipoints_path[-3:]
    else:
        file_suffix = filetype
    if file_suffix=="csv":
        positions = load_csv_multipoints(multipoints_path)
    elif file_suffix=="xml":
        positions = load_xml_multipoints(multipoints_path)
    else:
        raise ValueError('Filetype not recognized')
    return positions

def load_csv_multipoints(multipoints_path,scaling=1000.):
    with open(multipoints_path,"r") as infile:
        positions = infile.read()
    positions = positions.split("\n")[:-1]
    positions = [tuple(float(item)*scaling for item in position.split(";")) for position in positions]

    return positions

def parse_xml_position(e):
    return dict(
        name=e.find("strName").attrib["value"],
        checked=(e.find("bChecked").attrib["value"].lower() != "false"),
        x=float(e.find("dXPosition").attrib["value"]),
        y=float(e.find("dYPosition").attrib["value"]),
        z=float(e.find("dZPosition").attrib["value"]),
        pfs_offset=float(e.find("dPFSOffset").attrib["value"]),
    )

def load_xml_multipoints(filename):
    positions = []
    with open(filename, encoding="utf-16") as input:
        input_xml = ET.parse(input, parser=ET.XMLParser(encoding="utf-16"))
    for e in input_xml.findall("./no_name/*"):
        if e.tag not in ("bIncludeZ", "bPFSEnabled"):
            p = parse_xml_position(e)
            positions.append((p["x"], p["y"]))
    return positions

def check_grid_corners(scopeInstance,xy_grid,shift_tol=100,wait_time=0):
    xy_grid_arr = np.array(xy_grid)
    
    max_x,min_x = np.max(xy_grid_arr[:,0]),np.min(xy_grid_arr[:,0])
    max_y,min_y = np.max(xy_grid_arr[:,1]),np.min(xy_grid_arr[:,1])

    first_col_mask,last_col_mask = xy_grid_arr[:,0]>(max_x-shift_tol),xy_grid_arr[:,0]<(min_x+shift_tol)
    last_row_mask,first_row_mask = xy_grid_arr[:,1]>(max_y-shift_tol),xy_grid_arr[:,1]<(min_y+shift_tol) #inverted coords

    top_left = xy_grid_arr[first_col_mask&first_row_mask][0]
    top_right = xy_grid_arr[last_col_mask&first_row_mask][0]
    bottom_left = xy_grid_arr[first_col_mask&last_row_mask][0]
    bottom_right = xy_grid_arr[last_col_mask&last_row_mask][0]
    
    for selected_point in [top_left,top_right,bottom_right,bottom_left,top_left]:
        scopeInstance.mmc.setXYPosition(selected_point[0],selected_point[1])
        sleep(wait_time)

class scopeCore:
    def __init__(self,configpath,logpath,camera_name="BSI Prime",shutter_name="SpectraIII",xystage_name="XYStage",focus_name="ZDrive",fish_channel_group="FISH_channels"):
        self.mmc = pymmcore.CMMCore()
        self.mmc.loadSystemConfiguration(configpath)
        self.mmc.setPrimaryLogFile(logpath)
        self.mmc.setCameraDevice(camera_name)
        
        self.camera_name = camera_name
        self.shutter_name = shutter_name
        self.xystage_name = xystage_name
        self.focus_name = focus_name

    def snap_image(self,img_size=(12,12)):
        self.mmc.snapImage()
        im1 = self.mmc.getImage()
        return im1

    def auto_contrast(self,img,low_percentile=0,high_percentile=100):
        low = np.percentile(img,low_percentile)
        high = np.percentile(img,high_percentile)
        return low,high

    def plot_img(self,img,low,high,img_size=(12,12)):
        clear_output(wait = True)
        plt.figure(figsize=img_size)
        plt.imshow(img, interpolation='None',vmin=low,vmax=high)
        plt.show()
        
    def liveview(self,img_size=(12,12),low=None,high=None):#W,interval=0.5):
        while True:
            try:
                while self.mmc.deviceBusy(self.camera_name):
                    time.sleep(0.005)
                    
                im1 = self.snap_image()
                clear_output(wait = True)
                plt.figure(figsize=img_size)
                if low == None or high == None:
                    plt.imshow(im1, interpolation='None',cmap="gray")
                else:
                    plt.imshow(im1, interpolation='None',cmap="gray",vmin=low,vmax=high)
                plt.show()
            except KeyboardInterrupt:
                break
        while self.mmc.deviceBusy(self.camera_name):
            time.sleep(0.01)
            
    def set_grid(self,num_col,num_row,col_step=333.,row_step=686.):
        grid_coords = []

        x_ori,y_ori = self.mmc.getXYPosition()
        start_left = True

        for row in range(num_row):
            y_disp = row*row_step

            if start_left:
                for col in range(num_col):
                    x_disp = col*(-col_step)
                    current_coord = (x_ori+x_disp,y_ori+y_disp)
                    grid_coords.append(current_coord)
                start_left = False
            else:
                for col in range(num_col):
                    x_disp = (num_col-col-1)*(-col_step)
                    current_coord = (x_ori+x_disp,y_ori+y_disp)
                    grid_coords.append(current_coord)
                start_left = True

        return grid_coords
    
    
    def multipoint_aq(self,grid_coords,config_list,timepoint,output_folder="./",group_name="FISH_channels"):
        
        ### Make sure configs are valid ###
        undefined_configs = []
        for config in config_list:
            config_defined = self.mmc.isConfigDefined(group_name,config)
            if not config_defined:
                undefined_configs.append(config)
        
        if len(undefined_configs) > 0:
            raise ValueError("The following configs are undefined: " + ", ".join(undefined_configs))
            
        ### Gather basic metadata ###
            
        t_start = time.time()
        x_dim = self.mmc.getProperty(self.camera_name,"X-dimension")
        y_dim = self.mmc.getProperty(self.camera_name,"Y-dimension")
        
        ## Note change the write to disk later ##
                
        imgs = []
        imgs_metadata = []
        
        x_coord,y_coord = grid_coords[0]
        self.mmc.setXYPosition(x_coord,y_coord)

        for fov_num,(x_coord,y_coord) in enumerate(grid_coords):
            while self.mmc.deviceBusy(self.xystage_name):
                time.sleep(0.1)
                pass
            self.mmc.setXYPosition(x_coord,y_coord)                
            
            for config in config_list:
                while self.mmc.systemBusy():
                    time.sleep(0.1)
                    pass
                
                self.mmc.setConfig(group_name,config)
                    
                while self.mmc.systemBusy():
                    time.sleep(0.1)
                    pass
                
                if "noPFS" not in config:
                    self.mmc.setProperty("PFS","FocusMaintenance","On")
                    time.sleep(0.25)
                    
                shutter_failed = True
                while shutter_failed:
                    try:
                        self.mmc.setShutterOpen(self.shutter_name,True)
                        self.mmc.snapImage()
                        self.mmc.setShutterOpen(self.shutter_name,False)
                        shutter_failed = False
                    except:
                        time.sleep(0.25)

                read_x_coord,read_y_coord = self.mmc.getXYPosition(self.xystage_name)
                read_z_coord = self.mmc.getPosition(self.focus_name)
                current_time = time.time()-t_start
                
                metadata_entry = {"fov":fov_num,"config":config,"x":read_x_coord,"y":read_y_coord,"z":read_z_coord,"t":current_time}
                img = self.mmc.getImage()
                
                imgs.append(img)
                imgs_metadata.append(metadata_entry)
            while self.mmc.systemBusy():
                time.sleep(0.1)
                pass
            self.mmc.setConfig(group_name,config_list[0])
            while self.mmc.systemBusy():
                time.sleep(0.1)
                pass
            if "noPFS" not in config_list[0]:
                self.mmc.setProperty("PFS","FocusMaintenance","On")
                time.sleep(0.25)
        x_coord,y_coord = grid_coords[0]
        self.mmc.setXYPosition(x_coord,y_coord)
                
        for img_num in range(len(imgs)):
            img = imgs[img_num]
            metadata_entry = imgs_metadata[img_num]

            with h5py.File(output_folder + "fov=" + str(metadata_entry["fov"]) + "_config=" + str(metadata_entry["config"]) + "_t=" + str(timepoint) + ".hdf5","w") as h5pyfile:
                hdf5_dataset = h5pyfile.create_dataset("data", data=img, chunks=(128,128), dtype='uint16')
        
        metadata = pd.DataFrame.from_dict(imgs_metadata)
        metadata.to_hdf(output_folder + "metadata_" + str(timepoint) + ".hdf5", key="data", mode="w")