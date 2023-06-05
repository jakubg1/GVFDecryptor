import sys
import struct
import time

#FILE_NAME = "stagemap_stagenames_challenge_en.uis"
#FILE_NAME = "stagemap_survival_en.ui"
#FILE_NAME = "dialog_options_en.ui"
#FILE_NAME = "profiles.gvf"
#FILE_NAME = "2.gvf"
#FILE_NAME = "startup.sm"
#FILE_NAME = "instructions.sm"
#FILE_NAME = "achievements.sm"
#FILE_NAME = "mainmenu.sm"

MAX_UINT = 2**32 - 1
MAX_INT = 2**31 - 1

read_ptr = 0



def open_gvf_file(path):
	file = open(path, "rb")
	contents = file.read()
	file.close()
	
	return contents

def save_gvf_file(path, contents):
	file = open(path, "w")
	file.write(contents)
	file.close()



def read_bytes(data, bytes, big_endian = False):
	global read_ptr
	
	out = data[read_ptr:read_ptr+bytes]
	read_ptr += bytes
	if big_endian:
		out = out[::-1]
	return out

def read_int(data, bytes):
	bytes = read_bytes(data, bytes, True)
	num = 0
	for b in bytes:
		num = (num << 8) + b
	return num

def read_float4(data):
	bytes = read_bytes(data, 4, True)
	return struct.unpack(">f", bytes)[0]



def read_value(data, command, format):
	if format == 4 and command < 0x09:
		read_int(data, 3)
	
	if command == 0x00: # boolean
		return read_int(data, 1) == 1
	elif command == 0x01: # signed integer
		return (read_int(data, 4) + MAX_INT) % (MAX_UINT + 1) - MAX_INT
	elif command == 0x02: # unsigned integer
		return read_int(data, 4)
	elif command == 0x03: # a single float/array of floats
		return read_float4(data)
	elif command == 0x04: # 64-bit integer
		return read_int(data, 8)
	elif command == 0x05: # string
		string_length = read_int(data, 4)
		return read_bytes(data, string_length).decode()
	elif command == 0x06: # translated string
		string_length = read_int(data, 4)
		return read_bytes(data, string_length).decode()
	elif command == 0x08: # tilde reference
		string_length = read_int(data, 4)
		return read_bytes(data, string_length).decode()
	elif command == 0x09: # constant/enum
		string_length = read_int(data, 4)
		return read_bytes(data, string_length).decode()
	elif command == 0x0B: # constant/enum (used in state machines)
		string_length = read_int(data, 4)
		return read_bytes(data, string_length).decode()

def format_value(command, value):
	if command == 0x00: # boolean
		return "true" if value else "false"
	elif command == 0x01: # signed integer
		return str(value)
	elif command == 0x02: # unsigned integer
		return str(value)
	elif command == 0x03: # float
		return "{0:.6f}".format(value)
	elif command == 0x04: # 64-bit integer
		return str(value) + "i64"
	elif command == 0x05: # string
		return "\"" + value + "\""
	elif command == 0x06: # translated string
		return "T( \"" + value + "\" )"
	elif command == 0x08: # tilde reference
		return "~" + value
	elif command == 0x09: # constant/enum
		return value
	elif command == 0x0B: # constant/enum (used in state machines)
		return value

def format_values(command, values):
	if len(values) == 1:
		return format_value(command, values[0])
	else:
		return "[ " + ", ".join(format_value(command, value) for value in values) + " ]"



def main():
	if len(sys.argv) < 2 or len(sys.argv) > 3:
		print("Usage: python main.py <source> [destination]")
		print("If destination is not specified, the result will be printed to console.")
		return
	
	file_name = sys.argv[1]
	file_name_out = sys.argv[2] if len(sys.argv) >= 3 else None
	output = ""
	
	
	
	global read_ptr
	
	data = open_gvf_file(file_name)
	
	if read_bytes(data, 7) != b"\x01GVF002":
		print("File header does not match!")
		return
	format = read_int(data, 1)
	if format != 1 and format != 4:
		print("Unknown file format! (" + str(format) + ")")
		return
	print("Format: " + str(format))
	
	record_count = read_int(data, 4)
	print("Record count: " + str(record_count))
	records = []
	print("Records:")
	for i in range(record_count):
		record_length = read_int(data, 4)
		record_name = read_bytes(data, record_length).decode()
		records.append(record_name)
		print("    " + "{:02X}".format(i) + ": " + record_name)
	
	if read_bytes(data, 8) != b"\xff" * 8:
		print("Records have been read incorrectly!")
		return
	
	
	
	current_record = ""
	update_object_header = False
	current_object_header = None
	indent = 0
	
	while read_ptr < len(data):
		lines = []
		command = read_int(data, 1)
		
		if current_object_header != None and command != 0x13 and not update_object_header:
			lines.append("")
			lines.append(current_object_header)
			lines.append("{")
			lines.append(1)
			current_object_header = None
		
		if command == 0x13:
			record_id = read_int(data, 4)
			if record_id != MAX_UINT:
				current_record = records[record_id]
			else:
				current_record = ""
				update_object_header = True
		elif command <= 0x08: # primitives (see read_value, format_value functions above)
			length = read_int(data, 1)
			values = []
			for i in range(length):
				values.append(read_value(data, command, format))
			if not update_object_header:
				lines.append(current_record + " = " + format_values(command, values))
			else:
				# this field type serves as additional content to the current object header if it has been halted by the 0x13 command with -1 record
				current_object_header = current_object_header + " " + format_values(command, values)
		elif command == 0x09 or command == 0x0B: # constant/enum
			value = read_value(data, command, format)
			if not update_object_header:
				lines.append(current_record + " = " + format_value(command, value))
			else:
				# this field type serves as additional content to the current object header if it has been halted by the 0x13 command with -1 record
				current_object_header = current_object_header + " " + format_value(command, value)
		elif command == 0x11: # open object
			current_object_header = ""
			object_name_id = read_int(data, 4)
			if object_name_id != MAX_UINT:
				# object name (or type if the second field is "empty")
				object_name = records[object_name_id]
				current_object_header = object_name
			object_type_id = read_int(data, 4)
			if object_type_id != MAX_UINT:
				# object type specified
				object_type = records[object_type_id]
				current_object_header = object_type + " " + current_object_header
		elif command == 0x12: # close object
			if len(lines) >= 2 and lines[-2] == "{":
				# Avoid empty braces.
				lines.pop()
				lines.pop()
				lines.pop(-2)
			else:
				lines.append(-1)
				lines.append("}")
		elif command == 0x14: # include
			string_length = read_int(data, 4)
			string_contents = read_bytes(data, string_length).decode()
			lines.append("# " + string_contents)
		else:
			print("Unknown command! (" + str(command) + ") at byte " + "{:05X}".format(read_ptr))
			return
		
		if update_object_header and command != 0x13:
			update_object_header = False
		
		for line in lines:
			if type(line) is int:
				indent += line
			else:
				output += "\t" * indent + line + "\n"
	
	
	
	if file_name_out == None:
		print(output)
	else:
		save_gvf_file(file_name_out, output)



main()