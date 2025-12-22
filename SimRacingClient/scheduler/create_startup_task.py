import os
import subprocess

def create_startup_task(script_path, task_name="CommandServer"):
    python_path = subprocess.check_output(['where', 'python'], text=True).strip().split('\n')[0]
    
    xml_template = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Command execution server</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>{python_path}</Command>
      <Arguments>"{script_path}"</Arguments>
      <WorkingDirectory>{os.path.dirname(script_path)}</WorkingDirectory>
    </Exec>
  </Actions>
  <Principals>
    <Principal>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
</Task>'''
    
    xml_file = 'task.xml'
    with open(xml_file, 'w', encoding='utf-16') as f:
        f.write(xml_template)
    
    cmd = f'schtasks /Create /TN "{task_name}" /XML "{xml_file}" /F'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    os.remove(xml_file)
    
    if result.returncode == 0:
        print(f"Task '{task_name}' created successfully")
    else:
        print(f"Error: {result.stderr}")

if __name__ == '__main__':
    script_path = os.path.abspath('server.py')
    create_startup_task(script_path)