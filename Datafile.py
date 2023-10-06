import pandas as pd
import numpy as np
from DataProcessor import DataProcessor

HEADER_TIME = 'Time/s'
HEADER_T1 = 'T1/μ'
HEADER_T2 = 'T2/μ'

def data_to_file(data_processor: DataProcessor):
    df = pd.DataFrame()
    tm_arr = np.array(data_processor.time_array)
    t1_arr = np.array(data_processor.t1_array)
    t2_arr = np.array(data_processor.t2_array)
    df[HEADER_TIME] = tm_arr
    df[HEADER_T1] = t1_arr
    df[HEADER_T2] = t2_arr
    df.to_csv('test_data/data.csv', index=False,)
