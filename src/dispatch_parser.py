import re
import asyncio
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from src.log import logger

WEEKDAY_MAP = {
    '一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6,
    '月': 0, '火': 1, '水': 2, '木': 3, '金': 4, '土': 5, '日': 6
}

def parse_date(date_str: str) -> Optional[date]:
    """Parse date from format like '12/2' or '12/02' or '12／17' (fullwidth slash)"""
    try:
        # Support both ASCII slash (/) and fullwidth slash (／)
        match = re.search(r'(\d{1,2})[/／](\d{1,2})', date_str)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))

            current_year = datetime.now().year
            current_month = datetime.now().month

            # Special case: if current month is 12 and input is 1, it's next year
            if current_month == 12 and month == 1:
                year = current_year + 1
            else:
                year = current_year

            return date(year, month, day)
    except (ValueError, AttributeError):
        pass

    return None

def parse_date_range(date_str: str) -> List[date]:
    """Parse date range from formats like '12/25-27', '12/2-4', '12/25-7', or '11/19、20' (multiple dates with comma/Chinese comma)"""
    try:
        # Try to match date range with dash: M/D1-D2
        match = re.search(r'(\d{1,2})[/／](\d{1,2})-(\d{1,2})', date_str)
        if match:
            month = int(match.group(1))
            day_start = int(match.group(2))
            day_end = int(match.group(3))

            current_year = datetime.now().year
            current_month = datetime.now().month

            # Special case: if current month is 12 and input is 1, it's next year
            if current_month == 12 and month == 1:
                year = current_year + 1
            else:
                year = current_year

            # Generate list of dates
            dates = []

            # If day_end < day_start and day_end is single digit (1-9), 
            # it might be the ones digit of a two-digit number (e.g., 12/25-7 means 12/25-27)
            if day_end < day_start and day_end < 10 and day_start >= 20:
                # Try to construct the proper day_end (e.g., 7 -> 27)
                reconstructed_end = (day_start // 10) * 10 + day_end
                if reconstructed_end > day_start:
                    day_end = reconstructed_end

            for day in range(day_start, day_end + 1):
                try:
                    dates.append(date(year, month, day))
                except ValueError:
                    pass

            return dates if dates else []

        # Try to match date range with comma/Chinese comma: M/D1、D2 or M/D1, D2
        match = re.search(r'(\d{1,2})[/／](\d{1,2})[、,]\s*(\d{1,2})', date_str)
        if match:
            month = int(match.group(1))
            day1 = int(match.group(2))
            day2 = int(match.group(3))

            current_year = datetime.now().year
            current_month = datetime.now().month

            # Special case: if current month is 12 and input is 1, it's next year
            if current_month == 12 and month == 1:
                year = current_year + 1
            else:
                year = current_year

            dates = []
            try:
                dates.append(date(year, month, day1))
                dates.append(date(year, month, day2))
            except ValueError:
                pass

            return dates if dates else []

    except (ValueError, AttributeError):
        pass

    # Fall back to single date parsing
    single_date = parse_date(date_str)
    return [single_date] if single_date else []

def extract_cancelled_info(content: str) -> Optional[Dict[str, Any]]:
    """Extract cancellation info including date and task name
    Returns: {'date': date, 'task_name': str} or None"""
    if '取消' not in content:
        return None

    # Look for pattern like "原定11／11三分隊線巡取消" or "11／11取消"
    match = re.search(r'(\d{1,2})[/／](\d{1,2})([^\n取]*?)(?:取消|$)', content)
    if match:
        date_part = content[match.start(match.group(1)):match.end(match.group(2))]
        task_part = match.group(3).strip() if match.group(3) else ''

        cancelled_date = parse_date(date_part)
        if cancelled_date:
            return {
                'date': cancelled_date,
                'task_name': task_part
            }

    return None

def has_date(content: str) -> bool:
    """Check if a message contains a date pattern (12/5 or 12月5號 format)"""
    # ASCII slash format: 12/5
    if re.search(r'\d{1,2}[/／]\d{1,2}', content):
        return True
    # Chinese month format: 12月5號 or 12月5日
    if re.search(r'\d{1,2}月\d{1,2}[號日]?', content):
        return True
    return False

def is_dispatch_message(content: str) -> bool:
    """Check if a message contains dispatch information"""
    dispatch_keywords = ['派車', '待搶用車', '用車', '出車', '抗滑', '車長', '駕駛', '副隊', '人員載運']

    keyword_count = 0
    for keyword in dispatch_keywords:
        if keyword in content:
            keyword_count += 1

    if '車長' in content and '駕駛' in content:
        return True

    if '副隊' in content and '人員載運' in content:
        return True

    for keyword in ['派車', '待搶用車', '抗滑', '人員載運']:
        if keyword in content:
            return True

    # Also consider messages with cancellation
    if '取消' in content and any(kw in content for kw in ['派車', '線巡', '觀測', '佈纜', '佈覽']):
        return True

    return False


def extract_day_of_week(content: str) -> Optional[str]:
    """Extract day of week from content like (二) or (週二)"""
    patterns = [
        r'\(([一二三四五六日])\)',
        r'\(週([一二三四五六日])\)',
        r'（([一二三四五六日])）',
        r'（週([一二三四五六日])）'
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)

    return None

def extract_vehicle_plate(content: str) -> str:
    """Extract vehicle plate number (軍K-XXXXX format) from content"""
    pattern = r'(軍[A-Z]?-?\d+)'
    match = re.search(pattern, content)
    
    if match:
        plate = match.group(1)
        if not re.match(r'軍[A-Z]?-', plate):
            if re.match(r'軍[A-Z]\d', plate):
                plate = plate[0:2] + '-' + plate[2:]
            else:
                plate = '軍-' + plate[1:]
        return plate
    
    return ''

async def validate_task_name_with_ai(text: str) -> bool:
    """Use AI to validate if text is a military task name
    Returns True if text is likely a task name, False otherwise
    Falls back to True if AI is unavailable (keep the task name by default)
    """
    if not text or len(text.strip()) == 0:
        return False
    
    try:
        from src.aclient import discordClient
        provider_manager = discordClient.provider_manager
        current_provider = provider_manager.get_provider()
        
        prompt = f"""判斷以下文字是否為軍事任務名稱或派車任務說明。

文字: "{text}"

軍事任務名稱範例:
- 9A觀測所佈覽
- 三分隊線巡
- 連排線巡
- 95砲指揮車巡視
- 兩棲登陸演習

非任務名稱範例:
- 待搶用車
- 用車
- 派車
- 出車
- 人員載運
- 副隊
- 輜重隊
- 用車

請只回答 "是" 或 "否"，不要其他說明。"""

        messages = [{"role": "user", "content": prompt}]
        response = await current_provider.chat_completion(
            messages,
            model="auto"
        )
        
        result = response.strip().lower() if isinstance(response, str) else ""
        logger.info(f"[AI Task Validation] Text: '{text}' -> Response: '{result}'")
        
        # Check if AI response indicates "yes"
        is_valid = "是" in result or "yes" in result
        return is_valid
        
    except Exception as e:
        logger.warning(f"AI task validation failed: {e}")
        logger.info(f"[AI Task Validation] Keeping task name '{text}' (AI unavailable)")
        return True  # Return True to keep the task name if AI fails


def extract_task_name_field(content: str) -> str:
    """Extract task name from content
    Supports formats like:
    - 任務說明 9A觀測所佈覽
    - 任務說明: 9A觀測所佈覽
    - 12/25-7 9A觀測所佈纜 (task name after date)
    - Second line task name (when first line has date + plate)
    """
    # First try explicit task field patterns
    patterns = [
        r'任務說明[:：]?\s*(.+?)(?:\n|$)',
        r'任務[:：]\s*(.+?)(?:\n|$)',
        r'說明[:：]\s*(.+?)(?:\n|$)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            task = match.group(1).strip()
            task = re.sub(r'(車長|駕駛).*$', '', task).strip()
            if task:
                return task
    
    # Try to extract from first line after date pattern (like "12/25-7 9A觀測所佈纜")
    lines = content.strip().split('\n')
    first_line = lines[0].strip()
    
    # Pattern: date range/single date followed by task name
    # e.g. "12/25-7 9A觀測所佈纜" or "12/2(二) 9A觀測所佈纜"
    task_pattern = r'\d{1,2}[/／]\d{1,2}(?:-\d{1,2})?(?:\([一二三四五六日]\))?\s+(.+?)$'
    match = re.search(task_pattern, first_line)
    if match:
        extracted = match.group(1).strip()
        
        # Check for specific task keywords first (these should be preserved)
        task_keywords = ['人員載運用車', '線巡', '觀測', '佈纫', '佈覽', '抗滑', '預保', '搶修']
        for keyword in task_keywords:
            if keyword in extracted:
                return keyword
        
        # Remove vehicle plates (軍K-XXXXX format)
        extracted = re.sub(r'軍[A-Z]?\d*-\d+', '', extracted).strip()
        
        # If remaining text is NOT just a number, return it as task name
        if extracted and not re.match(r'^\d+$', extracted):
            return extracted
    
    # Try to find task name on second line
    # Format: Line 1 = date + plate, Line 2 = task name
    if len(lines) >= 2:
        second_line = lines[1].strip()
        
        # Check if first line has a vehicle plate
        has_plate = re.search(r'軍[A-Z]?-?\d+', first_line)
        
        if has_plate and second_line:
            # Keywords that indicate this line is NOT a task name
            skip_keywords = ['車長', '駕駛', '副隊', '任務說明', '任務:', '任務：', '說明:', '車號:', '車號：', '車牌:']
            is_skip_line = any(kw in second_line for kw in skip_keywords)
            
            # Check if line starts with a colon pattern (like "車長: XXX")
            is_field_line = re.match(r'^.+[:：]', second_line) and len(second_line.split(':')[0]) <= 4
            
            # Check if it's a status keyword only
            status_only = second_line in ['待搶用車', '用車', '出車', '派車']
            
            if not is_skip_line and not is_field_line and not status_only:
                # This is likely a task name - return as candidate for AI validation
                return second_line
    
    return ''

def extract_vehicle_info(content: str) -> List[Dict[str, str]]:
    """Extract vehicle ID and status from content
    
    Returns list of dicts with:
    - vehicle_id: unique identifier for deduplication (plate or task name)
    - vehicle_plate: actual vehicle plate number (軍K-XXXXX format) or empty
    - task_name: task description from 任務說明 field or extracted from first line
    - status: vehicle status like 待搶用車
    """
    vehicles = []
    seen_vehicles = set()

    first_line = content.split('\n')[0]

    # Extract task name from dedicated field first (like "任務說明 9A觀測所佈覽")
    task_name_from_field = extract_task_name_field(content)

    # Try to find military vehicle plate format (軍K-20539, 軍-20539, 軍1-23264, etc)
    plate_pattern = r'(軍[A-Z]?\d*-\d+)(待搶用車|用車|出車)?'
    plate_matches = re.findall(plate_pattern, content)

    for match in plate_matches:
        plate = match[0]

        # Normalize format to 軍-XXXX or 軍K-XXXX
        if not re.match(r'軍[A-Z]?-', plate):
            if re.match(r'軍[A-Z]\d', plate):
                plate = plate[0:2] + '-' + plate[2:]
            else:
                plate = '軍-' + plate[1:]

        if plate in seen_vehicles:
            continue
        seen_vehicles.add(plate)

        status = match[1] if len(match) > 1 and match[1] else ''
        if not status and '待搶用車' in content:
            status = '待搶用車'

        # Use plate as vehicle_id for dedup, store plate separately
        vehicles.append({
            'vehicle_id': plate,
            'status': status,
            'vehicle_plate': plate,
            'task_name': task_name_from_field
        })

    # If no military plate found, try plain numbers (like 590)
    if not vehicles:
        plain_pattern = r'\d{1,2}[/／]\d{1,2}\s+(\d+)'
        match = re.search(plain_pattern, first_line)
        if match:
            number_id = match.group(1)
            seen_vehicles.add(number_id)

            status = ''
            if '待搶用車' in content:
                status = '待搶用車'
            elif '人員載運' in content:
                status = '人員載運用車'

            vehicles.append({
                'vehicle_id': number_id,
                'status': status,
                'vehicle_plate': number_id,
                'task_name': task_name_from_field
            })

    # If no vehicle plate found but task_name exists, use task_name as vehicle_id
    # This allows task-only dispatch records to be processed
    if not vehicles and task_name_from_field:
        vehicles.append({
            'vehicle_id': task_name_from_field,
            'status': '',
            'vehicle_plate': '',
            'task_name': task_name_from_field
        })

    return vehicles

def extract_personnel(content: str) -> Dict[str, str]:
    """Extract commander and driver from content"""
    personnel = {
        'commander': '',
        'driver': ''
    }

    lines = content.split('\n')

    for i, line in enumerate(lines):
        line_stripped = line.strip()

        # Format 1: 車長:名字 或 駕駛:名字
        if '車長' in line:
            match = re.search(r'車長[:：\s]*([^\n\r駕駛:：]+)', line)
            if match:
                value = match.group(1).strip()
                if value and value not in [':', '：']:
                    personnel['commander'] = value

        if '駕駛' in line:
            match = re.search(r'駕駛[:：\s]*([^\n\r:：]+)', line)
            if match:
                value = match.group(1).strip()
                if value and value not in [':', '：']:
                    personnel['driver'] = value

        # Format 2: 副隊 楊修 (懶人格式)
        # "副隊" 是車長，後面的名字是駕駛
        if '副隊' in line_stripped and not personnel['commander']:
            personnel['commander'] = '副隊'
            # 從 "副隊 楊修" 中提取 "楊修" 作為駕駛
            match = re.search(r'副隊\s+(.+)$', line_stripped)
            if match:
                driver_name = match.group(1).strip()
                if driver_name:
                    personnel['driver'] = driver_name

    return personnel

def split_dispatch_blocks(content: str) -> List[str]:
    """Split content into separate dispatch blocks"""
    # Split by empty lines and then group lines that belong together
    lines = content.split('\n')
    blocks = []
    current_block = []

    for line in lines:
        stripped = line.strip()

        # Check if this line starts a new dispatch record
        # Either: has date + task keyword, or just has date (for simple format like "12/11三分隊線巡")
        has_date = re.match(r'\d{1,2}[/／]\d{1,2}', stripped)
        has_dispatch_keyword = any(kw in stripped for kw in ['派車', '用車', '觀測', '佈纜', '佈覽', '線巡', '搶修', '預保'])

        if has_date and (has_dispatch_keyword or len(current_block) == 0 or (len(current_block) > 0 and '車長' in '\n'.join(current_block))):
            # If we have a previous block, save it
            if current_block and ('車長' in '\n'.join(current_block) or '駕駛' in '\n'.join(current_block)):
                blocks.append('\n'.join(current_block))
            current_block = [line]
        elif stripped:  # Non-empty line
            if current_block:  # Only add if we're already in a block
                current_block.append(line)
        # Empty lines are skipped

    # Don't forget the last block
    if current_block and ('車長' in '\n'.join(current_block) or '駕駛' in '\n'.join(current_block) or re.match(r'\d{1,2}[/／]\d{1,2}', current_block[0].strip())):
        blocks.append('\n'.join(current_block))

    return blocks

def parse_single_dispatch_block(content: str) -> Optional[List[Dict[str, Any]]]:
    """Parse a single dispatch block and return records for each date"""
    dispatch_dates = parse_date_range(content)
    if not dispatch_dates:
        return None

    day_of_week = extract_day_of_week(content)
    vehicles = extract_vehicle_info(content)
    personnel = extract_personnel(content)

    logger.info(f"[DEBUG] parse_single_dispatch_block: dates={dispatch_dates}, vehicles={vehicles}, commander={personnel['commander']}, driver={personnel['driver']}")

    # Create a record for each date in the range
    results = []
    for dispatch_date in dispatch_dates:
        result = {
            'date': dispatch_date,
            'day_of_week': day_of_week or '',
            'vehicles': vehicles,
            'commander': personnel['commander'],
            'driver': personnel['driver']
        }
        results.append(result)

    return results


def parse_dispatch_message(content: str) -> Optional[List[Dict[str, Any]]]:
    """Parse a complete dispatch message and extract all information
    Returns a list of dispatch records (supports multiple dispatch blocks)"""
    if not is_dispatch_message(content):
        return None

    # Split into individual dispatch blocks
    blocks = split_dispatch_blocks(content)
    if not blocks:
        return None

    all_results = []
    for block in blocks:
        if is_dispatch_message(block):
            block_results = parse_single_dispatch_block(block)
            if block_results:
                all_results.extend(block_results)

    if all_results:
        logger.info(f"Parsed dispatch message: {len(all_results)} record(s) from {len(blocks)} block(s)")
        return all_results

    return None

def format_dispatch_for_display(dispatch: Dict[str, Any]) -> str:
    """Format a single dispatch record for display"""
    date_str = dispatch.get('dispatch_date', '')
    if isinstance(date_str, str):
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            weekday_names = ['一', '二', '三', '四', '五', '六', '日']
            day_of_week = weekday_names[d.weekday()]
            date_display = f"{d.month}/{d.day}({day_of_week})"
        except:
            date_display = date_str
    else:
        date_display = str(date_str)

    vehicle_id = dispatch.get('vehicle_id', '')
    vehicle_status = dispatch.get('vehicle_status', '待搶用車')
    commander = dispatch.get('commander', '')
    driver = dispatch.get('driver', '')

    lines = []

    # Only add date + vehicle_id line if vehicle_id exists
    if vehicle_id:
        lines.append(f"**{date_display}   {vehicle_id}{vehicle_status}**")

    lines.append(f"車長: {commander}")
    lines.append(f"駕駛: {driver}")

    return '\n'.join(lines)

def format_dispatch_list(dispatches: List[Dict[str, Any]]) -> str:
    """Format a list of dispatch records for display"""
    if not dispatches:
        return "目前沒有派車資訊。"

    grouped = {}
    for dispatch in dispatches:
        date_key = dispatch.get('dispatch_date', '')
        if date_key not in grouped:
            grouped[date_key] = []
        grouped[date_key].append(dispatch)

    output_lines = ["📋 **派車表單**", ""]

    sorted_dates = sorted(grouped.keys(), key=lambda x: datetime.strptime(x, '%Y-%m-%d').date())

    for idx, date_key in enumerate(sorted_dates):
        try:
            d = datetime.strptime(date_key, '%Y-%m-%d').date()
            weekday_names = ['一', '二', '三', '四', '五', '六', '日']
            day_of_week = weekday_names[d.weekday()]
            date_display = f"{d.month}/{d.day}({day_of_week})"
        except:
            date_display = date_key

        for dispatch in grouped[date_key]:
            vehicle_plate = dispatch.get('vehicle_plate', '') or ''
            task_name = dispatch.get('task_name', '') or ''
            vehicle_id = dispatch.get('vehicle_id', '') or ''
            commander = dispatch.get('commander', '') or ''
            driver = dispatch.get('driver', '') or ''

            # Skip if no task name
            if not task_name:
                continue

            # Always show date first
            output_lines.append(f"{date_display}")
            # Always show task name
            output_lines.append(f"任務: {task_name}")
            # Show vehicle plate if it exists
            if vehicle_plate:
                output_lines.append(f"車號: {vehicle_plate}")
            # Show commander and driver
            output_lines.append(f"車長: {commander}")
            output_lines.append(f"駕駛: {driver}")
            output_lines.append("")

        # Add separator line between different dates
        if idx < len(sorted_dates) - 1:
            output_lines.append("─" * 20)
            output_lines.append("")

    return '\n'.join(output_lines)
