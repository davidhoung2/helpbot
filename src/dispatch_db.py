import sqlite3
import os
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from src.log import logger

DB_PATH = os.getenv("DISPATCH_DB_PATH", "dispatch.db")

def get_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the dispatch database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dispatch (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispatch_date DATE NOT NULL,
            day_of_week TEXT,
            vehicle_id TEXT NOT NULL,
            vehicle_status TEXT,
            vehicle_plate TEXT,
            task_name TEXT,
            commander TEXT,
            driver TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            message_id TEXT,
            channel_id TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_dispatch_date ON dispatch(dispatch_date)
    ''')
    
    cursor.execute("PRAGMA table_info(dispatch)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'vehicle_plate' not in columns:
        cursor.execute('ALTER TABLE dispatch ADD COLUMN vehicle_plate TEXT')
        logger.info("Added vehicle_plate column to dispatch table")
    
    if 'task_name' not in columns:
        cursor.execute('ALTER TABLE dispatch ADD COLUMN task_name TEXT')
        logger.info("Added task_name column to dispatch table")
    
    conn.commit()
    conn.close()
    logger.info("Dispatch database initialized")

def add_dispatch(dispatch_date: date, day_of_week: str, vehicle_id: str, 
                 vehicle_status: str = "", commander: str = "", driver: str = "",
                 message_id: str = "", channel_id: str = "",
                 vehicle_plate: str = "", task_name: str = "") -> Optional[int]:
    """Add a new dispatch record"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO dispatch (dispatch_date, day_of_week, vehicle_id, vehicle_status, 
                             commander, driver, message_id, channel_id,
                             vehicle_plate, task_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (dispatch_date.isoformat(), day_of_week, vehicle_id, vehicle_status,
          commander, driver, message_id, channel_id, vehicle_plate, task_name))
    
    dispatch_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Added dispatch record: {dispatch_date} - {vehicle_id} (plate: {vehicle_plate}, task: {task_name})")
    return dispatch_id


def find_existing_dispatch(dispatch_date: date, vehicle_id: str = "", vehicle_plate: str = "", task_name: str = "") -> tuple[Optional[Dict[str, Any]], str]:
    """Find existing dispatch record by date + vehicle_id/plate or date + task_name
    
    Returns tuple of (existing_record, match_type) where match_type is:
    - 'vehicle_plate': matched by vehicle plate
    - 'vehicle_id': matched by vehicle ID
    - 'task_only': matched by task name only (both records lack vehicle identifiers)
    - 'none': no match found
    
    Priority: 
    1. Match by date + vehicle_plate (if provided and non-empty)
    2. Match by date + vehicle_id (if it looks like a vehicle ID, not a task name)
    3. Match by date + task_name ONLY if incoming record has no vehicle identifier
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    existing_record = None
    match_type = 'none'
    
    has_vehicle_plate = bool(vehicle_plate and vehicle_plate.strip())
    is_vehicle_id = vehicle_id and vehicle_id.startswith('軍')
    
    if has_vehicle_plate:
        cursor.execute('''
            SELECT * FROM dispatch 
            WHERE dispatch_date = ? AND vehicle_plate = ?
        ''', (dispatch_date.isoformat(), vehicle_plate))
        row = cursor.fetchone()
        if row:
            existing_record = dict(row)
            match_type = 'vehicle_plate'
    
    if not existing_record and is_vehicle_id:
        cursor.execute('''
            SELECT * FROM dispatch 
            WHERE dispatch_date = ? AND vehicle_id = ?
        ''', (dispatch_date.isoformat(), vehicle_id))
        row = cursor.fetchone()
        if row:
            existing_record = dict(row)
            match_type = 'vehicle_id'
    
    if not existing_record and task_name and not has_vehicle_plate and not is_vehicle_id:
        cursor.execute('''
            SELECT * FROM dispatch 
            WHERE dispatch_date = ? AND task_name = ? 
            AND (vehicle_plate IS NULL OR vehicle_plate = '')
            AND (vehicle_id IS NULL OR vehicle_id = ? OR vehicle_id NOT LIKE '軍%')
        ''', (dispatch_date.isoformat(), task_name, task_name))
        row = cursor.fetchone()
        if row:
            existing_record = dict(row)
            match_type = 'task_only'
    
    conn.close()
    return existing_record, match_type


def upsert_dispatch(dispatch_date: date, day_of_week: str, vehicle_id: str, 
                    vehicle_status: str = "", commander: str = "", driver: str = "",
                    message_id: str = "", channel_id: str = "",
                    vehicle_plate: str = "", task_name: str = "") -> tuple[Optional[int], str]:
    """Add or update a dispatch record
    
    Logic:
    1. If date + vehicle_plate/vehicle_id match exists -> update with new data (always)
    2. If date + task_name match exists (both lack vehicle identifiers) AND personnel changed -> update
    3. If date + task_name match exists (both lack vehicle identifiers) but personnel unchanged -> skip
    4. Otherwise -> insert new record
    
    Returns:
        tuple: (dispatch_id, action) where action is 'inserted', 'updated', 'skipped', or None on error
    """
    existing, match_type = find_existing_dispatch(dispatch_date, vehicle_id, vehicle_plate, task_name)
    
    if existing:
        old_commander = existing.get('commander', '') or ''
        old_driver = existing.get('driver', '') or ''
        
        personnel_changed = (commander != old_commander) or (driver != old_driver)
        
        if match_type == 'task_only' and not personnel_changed:
            logger.info(f"Skipped dispatch update (no changes): {dispatch_date} - {vehicle_id} (plate: {vehicle_plate}, task: {task_name})")
            return existing['id'], 'skipped'
        
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE dispatch 
            SET day_of_week = ?,
                vehicle_id = ?,
                vehicle_status = ?,
                vehicle_plate = ?,
                task_name = ?,
                commander = ?,
                driver = ?,
                message_id = ?,
                channel_id = ?
            WHERE id = ?
        ''', (day_of_week, vehicle_id, vehicle_status, vehicle_plate, task_name,
              commander, driver, message_id, channel_id, existing['id']))
        
        conn.commit()
        conn.close()
        
        old_info = f"車長:{old_commander} 駕駛:{old_driver}"
        new_info = f"車長:{commander} 駕駛:{driver}"
        logger.info(f"Updated dispatch record: {dispatch_date} - {vehicle_id} (plate: {vehicle_plate}, task: {task_name}) [{old_info}] -> [{new_info}] (matched by {match_type})")
        return existing['id'], 'updated'
    else:
        dispatch_id = add_dispatch(
            dispatch_date=dispatch_date,
            day_of_week=day_of_week,
            vehicle_id=vehicle_id,
            vehicle_status=vehicle_status,
            commander=commander,
            driver=driver,
            message_id=message_id,
            channel_id=channel_id,
            vehicle_plate=vehicle_plate,
            task_name=task_name
        )
        return dispatch_id, 'inserted'

def get_all_active_dispatches() -> List[Dict[str, Any]]:
    """Get all non-expired dispatch records"""
    conn = get_connection()
    cursor = conn.cursor()
    
    today = date.today().isoformat()
    cursor.execute('''
        SELECT * FROM dispatch 
        WHERE dispatch_date >= ?
        ORDER BY dispatch_date ASC, vehicle_id ASC
    ''', (today,))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_dispatches_by_date(target_date: date) -> List[Dict[str, Any]]:
    """Get dispatch records for a specific date"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM dispatch 
        WHERE dispatch_date = ?
        ORDER BY vehicle_id ASC
    ''', (target_date.isoformat(),))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def delete_expired_dispatches() -> int:
    """Delete all expired dispatch records (date has passed)"""
    conn = get_connection()
    cursor = conn.cursor()
    
    today = date.today().isoformat()
    cursor.execute('''
        DELETE FROM dispatch WHERE dispatch_date < ?
    ''', (today,))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        logger.info(f"Deleted {deleted_count} expired dispatch records")
    
    return deleted_count

def check_duplicate(dispatch_date: date, vehicle_id: str) -> bool:
    """Check if a dispatch record already exists"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) FROM dispatch 
        WHERE dispatch_date = ? AND vehicle_id = ?
    ''', (dispatch_date.isoformat(), vehicle_id))
    
    count = cursor.fetchone()[0]
    conn.close()
    
    return count > 0

def update_dispatch(dispatch_id: int, commander: Optional[str] = None, driver: Optional[str] = None) -> bool:
    """Update commander and/or driver for a dispatch record"""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if commander is not None:
        updates.append("commander = ?")
        params.append(commander)
    
    if driver is not None:
        updates.append("driver = ?")
        params.append(driver)
    
    if not updates:
        return False
    
    params.append(dispatch_id)
    query = f"UPDATE dispatch SET {', '.join(updates)} WHERE id = ?"
    
    cursor.execute(query, params)
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated

def delete_dispatch(dispatch_id: int) -> bool:
    """Delete a specific dispatch record"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM dispatch WHERE id = ?', (dispatch_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def get_dispatch_count() -> int:
    """Get total count of active dispatches"""
    conn = get_connection()
    cursor = conn.cursor()
    
    today = date.today().isoformat()
    cursor.execute('SELECT COUNT(*) FROM dispatch WHERE dispatch_date >= ?', (today,))
    count = cursor.fetchone()[0]
    conn.close()
    
    return count

def delete_dispatch_by_date(dispatch_date: date, task_name: str = "") -> int:
    """Delete dispatch records for a specific date
    If task_name is provided, only delete records matching that task name
    Otherwise, delete all records for that date"""
    conn = get_connection()
    cursor = conn.cursor()
    
    if task_name:
        # Match by vehicle_id or any field containing the task name
        # The task name is typically stored in vehicle_id field
        cursor.execute(
            'DELETE FROM dispatch WHERE dispatch_date = ? AND (vehicle_id LIKE ? OR vehicle_status LIKE ?)',
            (dispatch_date.isoformat(), f'%{task_name}%', f'%{task_name}%')
        )
    else:
        cursor.execute('DELETE FROM dispatch WHERE dispatch_date = ?', (dispatch_date.isoformat(),))
    
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        task_info = f" (task: {task_name})" if task_name else ""
        logger.info(f"Deleted {deleted_count} dispatch records for {dispatch_date}{task_info}")
    
    return deleted_count

def clear_all_dispatches() -> int:
    """Delete all dispatch records"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM dispatch')
    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()
    
    logger.info(f"Cleared all {deleted_count} dispatch records")
    return deleted_count
