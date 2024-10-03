import os
from time import sleep
import h5py

def wait_for(num_secs):
    num_secs = int(num_secs)
    for t in range(num_secs):
        sleep(1.)

class FISH_scheduler:
    def __init__(self,handlerInstance,scopeInstance=None,skip_fixation=False,include_wash_cycle=False,fast_speed=2000,medium_speed=300,slow_speed=100,\
                 mins_fast_speed=4.,mins_medium_speed=5.,channels=["BF","GFP","Cy5","Cy7"],output_folder="./"):
        self.handlerInstance = handlerInstance
        self.scopeInstance = scopeInstance
        self.skip_fixation = skip_fixation
        self.include_wash_cycle = include_wash_cycle
        self.fast_speed = fast_speed
        self.medium_speed = medium_speed
        self.slow_speed = slow_speed
        
        self.secs_fast_speed = int(mins_fast_speed*60)
        self.secs_medium_speed = int(mins_medium_speed*60)
        
        if scopeInstance is None:
            self.no_scope = True
        else:
            self.no_scope = False
        
        self.channels = channels                                          
        self.output_folder = output_folder
            
    def load_reagent(self,reagent_name):
        print(reagent_name)
        
        self.handlerInstance.set_pump_state(0)
        self.handlerInstance.set_valve_state(reagent_name,1)
        self.handlerInstance.set_pump_state(self.fast_speed)
        
        wait_for(self.secs_fast_speed)
    
        self.handlerInstance.set_pump_state(self.medium_speed)
        self.handlerInstance.set_valve_state(reagent_name,0)

        wait_for(self.secs_medium_speed)
        return True
        
    def init_fixation(self):
        self.load_reagent("PFA(half-MeAc)")
        print("Initialized.")
        
    def continue_fixation(self):
        self.load_reagent("EtOH(MeAc)")
        self.handlerInstance.set_pump_state(self.slow_speed)
        wait_for(45*60)
        self.load_reagent("PFA(half-MeAc)")
        print("Fixed.")
        
    def perform_cycle(self,cycle_num,no_cleave=False):
        reagent_name = "Probe " + str(cycle_num)
        
        if not no_cleave:
            self.load_reagent("Cleave")
            wait_for(10*60)

        if self.include_wash_cycle:
            self.load_reagent("SSC")
            self.handlerInstance.set_pump_state(self.slow_speed)
            self.wait_for(3*60)
            
        self.load_reagent(reagent_name)
        self.handlerInstance.set_pump_state(self.slow_speed)
        wait_for(30*60)
        self.load_reagent("Image")
        wait_for(5*60)
        self.handlerInstance.set_pump_state(self.slow_speed)
        
    def run(self,grid_coords=None,num_cycles=10):
        if not os.path.exists(self.output_folder):
            os.makedir(self.output_folder)
        
        if not self.skip_fixation:
        
            if not self.no_scope:
                first_x,first_y = grid_coords[0]
                self.scopeInstance.mmc.setXYPosition(first_x,first_y)

                img = self.scopeInstance.snap_image()

                with h5py.File(self.output_folder + "initial.hdf5","w") as h5pyfile:
                    hdf5_dataset = h5pyfile.create_dataset("data", data=img, chunks=(128,128), dtype='uint16')

            self.init_fixation()

            if not self.no_scope:

                img = self.scopeInstance.snap_image()

                with h5py.File(self.output_folder + "init_fixation.hdf5","w") as h5pyfile:
                    hdf5_dataset = h5pyfile.create_dataset("data", data=img, chunks=(128,128), dtype='uint16')

            self.continue_fixation()

            if not self.no_scope:
                img = self.scopeInstance.snap_image()

                with h5py.File(self.output_folder + "fixed.hdf5","w") as h5pyfile:
                    hdf5_dataset = h5pyfile.create_dataset("data", data=img, chunks=(128,128), dtype='uint16')

        for c in range(1,num_cycles+1):
            if c == 1:
                self.perform_cycle(c,no_cleave=True)
            else:
                self.perform_cycle(c)
            
            if not self.no_scope:
                print("Imageing...")

                self.scopeInstance.multipoint_aq(grid_coords,self.channels,c,output_folder=self.output_folder)
                
        self.handlerInstance.set_pump_state(0)
        self.handlerInstance.set_valve_state("SSC",0)
        self.handlerInstance.set_pump_state(self.slow_speed)