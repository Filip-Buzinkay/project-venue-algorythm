R2 and WallE are the main state machine algorythms - almost the same with few different traits for 
faster overall seatch - having two sensors 1 distance able to detect cube or maintains; 
1 color able to detec craters and wall map boundaries (only in the close range) simulating
reals project sensor limitations

heat_map is the 3d internal map of both robots recording the 2d coordinate + number of visits 
to eliminate looping and rediscovering of the same area

back_bone stores functions used for simulation generation and rebots 

venus is the simulation environment map having cubes that should be discovered space bariers as walls and 
obstacles - mountain (big square) craters (ellipses)

main.py starts the robots and simulation and connects them together with zmq to communicate real time
robots sending their coordinates and direction and simulation sending back the sensor output to simulate real life
testing 

needs zmq, python, pygame