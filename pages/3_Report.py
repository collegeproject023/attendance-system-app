import streamlit as st 
import pandas as pd
from Home import face_rec
st.set_page_config(page_title='Reporting',layout='wide')
st.subheader('Reporting')


# Retrive logs data and show in Report.py
# extract data from redis list
name = 'attendance:logs'
def load_logs(name,end=-1):
    logs_list = face_rec.r.lrange(name,start=0,end=end) # extract all data from the redis database
    return logs_list

# tabs to show the info
tab1, tab2, tab3 = st.tabs(['Registered Data','Logs', 'Attendance Report'])

with tab1:
    if st.button('Refresh Data'):
        # Retrive the data from Redis Database
        with st.spinner('Retriving Data from Redis DB ...'):    
            redis_face_db = face_rec.retrive_data(name='academy:register')
            st.dataframe(redis_face_db[['Name','Role']])

with tab2:
    if st.button('Refresh Logs'):
        st.write(load_logs(name=name))

with tab3:
    st.subheader('Attendance Report')
    
    # Load logs into attribute logs_list
    logs_list = load_logs(name=name)

    # Step 1: Convert the logs that in list of bytes into list of string
    convert_byte_to_string = lambda x: x.decode('utf-8')
    logs_list_string = list(map(convert_byte_to_string, logs_list))

    # Step 2: Split string by @ and create nested list
    split_string = lambda x: x.split('@')
    logs_nested_list = list(map(split_string, logs_list_string))

    # Convert nested list info into dataframe
    logs_df = pd.DataFrame(logs_nested_list, columns= ['Name','Role','Timestamp'])

# Step 3: Time base Analysis or Report Time-In Time-out
    logs_df['Timestamp'] = pd.to_datetime(logs_df['Timestamp'])
    logs_df['Date'] = logs_df['Timestamp'].dt.date

# Step 3.1: Calculate Report Time-In Time-out
# In Time: At which person is first detected in that day (min Timestamp of the date)
# Out Time: At which person is last detected in that day (max Timestamp of the date)

    report_df = logs_df.groupby(by=['Date','Name','Role']).agg(
        In_time = pd.NamedAgg('Timestamp','min'), # In Time
        Out_time = pd.NamedAgg('Timestamp','max') # Out Time
    ).reset_index()

    report_df['In_time'] = pd.to_datetime(report_df['In_time'])
    report_df['Out_time'] = pd.to_datetime(report_df['Out_time'])

    report_df['Duration'] = report_df['Out_time'] - report_df['In_time']

# Step 4: Marking Person is Present or Absent
    all_dates = report_df['Date'].unique()
    name_role = report_df[['Name','Role']].drop_duplicates().values.tolist()

    date_name_rol_zip_df = []
    for dt in all_dates:
        for name, role in name_role:
            date_name_rol_zip_df.append([dt, name, role])

    date_name_rol_zip_df = pd.DataFrame(date_name_rol_zip_df, columns=['Date','Name','Role'])

    # lef join with report_df
    date_name_rol_zip_df = pd.merge(date_name_rol_zip_df, report_df, how='left',on=['Date','Name','Role'])

    # Duration
    # Hours
    date_name_rol_zip_df['Duration_seconds'] = date_name_rol_zip_df['Duration'].dt.seconds
    date_name_rol_zip_df['Duration_hours'] = date_name_rol_zip_df['Duration_seconds'] / (60*60)

    def status_marker(x):

        if pd.Series(x).isnull().all():
            return 'Absent'
        
        elif x >= 0 and x < 1:
            return 'Late'
        
        elif x >= 2 and x <= 10:
            return 'Present'
        
    date_name_rol_zip_df['Status'] = date_name_rol_zip_df['Duration_hours'].apply(status_marker)

    # Convert 'Date' column to datetime if it's not already
date_name_rol_zip_df['Date'] = pd.to_datetime(date_name_rol_zip_df['Date'])

# Set 'Date' as the index
date_name_rol_zip_df.set_index('Date', inplace=True)

# Step 5: Weekly Report
weekly_report = date_name_rol_zip_df.groupby(['Name','Role', pd.Grouper(freq='W-Mon')]).agg(
    Total_Present=pd.NamedAgg(column='Status', aggfunc=lambda x: (x == 'Present').sum()),
    Total_Absent=pd.NamedAgg(column='Status', aggfunc=lambda x: (x == 'Absent').sum())
).reset_index()

# Step 6: Monthly Report
monthly_report = date_name_rol_zip_df.groupby(['Name','Role', pd.Grouper(freq='M')]).agg(
    Total_Present=pd.NamedAgg(column='Status', aggfunc=lambda x: (x == 'Present').sum()),
    Total_Absent=pd.NamedAgg(column='Status', aggfunc=lambda x: (x == 'Absent').sum())
).reset_index()

# Reset the index in the original dataframe
date_name_rol_zip_df.reset_index(inplace=True)

# Display the weekly report
st.subheader('Weekly Attendance Report')
st.dataframe(weekly_report, column_order=['Date', 'Name', 'Role', 'Total_Present', 'Total_Absent'])

# Display the monthly report
st.subheader('Monthly Attendance Report')
st.dataframe(monthly_report, column_order=['Date', 'Name', 'Role', 'Total_Present', 'Total_Absent'])

# Your existing code to display daily report
st.subheader('Daily Attendance Report')
st.dataframe(date_name_rol_zip_df, column_order=['Date', 'Name', 'Role', 'In_time', 'Out_time', 'Status'])
