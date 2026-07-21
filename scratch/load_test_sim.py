# -*- coding: utf-8 -*-
import time
from datetime import datetime, timedelta
from odoo import api, SUPERUSER_ID

# Set to True if you want to keep the records in the DB to inspect them or test the UI dashboard.
# Set to False if you only want to measure performance/load testing and clean up immediately.
COMMIT_TO_DB = False

def run_simulation(env):
    print("=============================================================")
    print("STARTING LOCATION TRACKING LOAD TESTING SIMULATION")
    print(f"COMMIT TO DATABASE: {COMMIT_TO_DB}")
    print("Scenario: 300 Employees, 1-Hour Sync Batches (6 points/employee)")
    print("=============================================================")

    # 1. Setup mock data
    print("\n[Step 1] Preparing mock employees and attendances...")
    company = env.company
    employee_count = 300
    points_per_employee = 6

    # Create mock employees
    start_time = time.time()
    employee_vals = [
        {
            'name': f'Mock Sales Officer {i}',
            'company_id': company.id,
            'active': True,
        }
        for i in range(employee_count)
    ]
    employees = env['hr.employee'].create(employee_vals)
    print(f"-> Created {len(employees)} mock employees in {time.time() - start_time:.4f} seconds.")

    # Create mock attendance shifts
    start_time = time.time()
    check_in_time = datetime.now() - timedelta(hours=2)
    attendance_vals = [
        {
            'employee_id': emp.id,
            'check_in': check_in_time,
        }
        for emp in employees
    ]
    attendances = env['hr.attendance'].create(attendance_vals)
    print(f"-> Created {len(attendances)} mock attendance shifts in {time.time() - start_time:.4f} seconds.")

    # 2. Simulate Batch Sync (Bulk Insert)
    print("\n[Step 2] Simulating bulk location sync (1,800 coordinate logs)...")
    location_vals = []
    base_time = datetime.now() - timedelta(hours=1)
    
    for idx, emp in enumerate(employees):
        att = attendances[idx]
        for p in range(points_per_employee):
            log_time = base_time + timedelta(minutes=10 * p)
            location_vals.append({
                'employee_id': emp.id,
                'attendance_id': att.id,
                'latitude': 23.8103 + (idx * 0.0001) + (p * 0.00005),
                'longitude': 90.4125 + (idx * 0.0001) + (p * 0.00005),
                'recorded_at': log_time,
                'is_mock': False,
            })

    # Measure bulk creation
    start_time = time.time()
    created_locations = env['sales.employee.location'].create(location_vals)
    duration = time.time() - start_time
    print(f"-> Successfully inserted {len(created_locations)} coordinate points in {duration:.4f} seconds.")
    print(f"-> Average insertion rate: {len(created_locations) / duration:.2f} rows/second.")

    # 3. Simulate Dashboard Map Queries (Read Speed)
    print("\n[Step 3] Simulating dashboard reads (fetching coordinates for a shift)...")
    read_times = []
    import random
    test_attendances = random.sample(attendances, min(50, len(attendances)))
    
    for att in test_attendances:
        r_start = time.time()
        points = env['sales.employee.location'].search_read(
            [('attendance_id', '=', att.id)],
            ['latitude', 'longitude', 'recorded_at', 'is_mock'],
            order='recorded_at asc'
        )
        read_times.append(time.time() - r_start)
    
    avg_read_time = sum(read_times) / len(read_times)
    print(f"-> Checked {len(test_attendances)} random shifts.")
    print(f"-> Average read/render query time: {avg_read_time * 1000:.2f} milliseconds per shift.")

    # 4. Clean up mock records OR Commit transaction
    if not COMMIT_TO_DB:
        print("\n[Step 4] Cleaning up mock records from database...")
        start_time = time.time()
        created_locations.unlink()
        attendances.unlink()
        employees.unlink()
        print(f"-> Database cleaned up in {time.time() - start_time:.4f} seconds.")
        print("-> (No changes were saved to PostgreSQL.)")
    else:
        print("\n[Step 4] Committing mock records to PostgreSQL database...")
        env.cr.commit()
        print("-> Done. Mock records have been saved permanently.")
        print(f"-> You can view 'Mock Sales Officer 0' etc. on the map dashboard.")

    print("=============================================================")
    print("SIMULATION COMPLETED SUCCESSFULLY")
    print("=============================================================")

# Execute the simulation
if 'env' in globals():
    run_simulation(globals()['env'])
