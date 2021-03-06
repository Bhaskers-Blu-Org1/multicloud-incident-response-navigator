import curses
import sys, requests, copy
from typing import Dict, Tuple

import skipper_helpers as shs
import curses_helpers as chs
import left_window as lwin
import top_window as twin
import search_bar as sb
import right_window as rwin

def run_skipper(stdscr):
	"""
	Runs the Skipper interactive terminal application until user quits.

	:param (_curses.window) stdscr:
					Automatically passed in by curses.wrapper function.
					A _curses.window obj that represents the entire screen.
	:return: None
	"""

	START_MODE = "cluster"	# possible modes include app, cluster, query, anomaly
	START_FTYPE = "summary"
	START_PANEL = "left"
	# initialize stdscr (standard screen)
	stdscr = chs.initialize_curses()
	height, width = stdscr.getmaxyx()

	# if terminal size doesn't meet requirements
	if height < 40 or width < 178:
		shs.terminal_size_reminder(stdscr)
		return

	# on startup, show loading screen
	# get the data for the initial cluster mode screen that lists all clusters
	fetch_data = lambda: requests.get('http://127.0.0.1:5000/start/{}'.format(START_MODE)).json()
	data = shs.loading_screen(stdscr, task=fetch_data)
	stdscr.erase()
	stdscr.refresh()

	mode = START_MODE
	ftype = START_FTYPE
	panel_side = START_PANEL

	# initialize and draw top window
	twin.init_win(len(shs.figlet_lines()) + 3, width, 0,0, data['has_apps'])	# height, width, y, x, has_apps
	twin.draw(mode=mode, ftype=ftype, panel=panel_side)
	twin.init_load(mode)
	top_height, top_width = twin.window.getmaxyx()
	panel_height = height-top_height
	panel_width = width//2

	# initialize and draw windows
	lwin.init_win(stdscr, height=panel_height, width=panel_width, y=top_height, x=0)
	rwin.init(panel_height, panel_width, top_height)

	if len(data['table_items']) > 0:
		table_data = {	"mode": START_MODE,
						"col_names": ["kind", "name"],
						"col_widths": lwin.get_column_widths([1/6, 5/6]),
						"table": [[t_item['rtype'], t_item['name']] for t_item in data['table_items']],
						"row_selector": data['index'],
						"start_y": 0,
						"path_names": data['path_names'],
						"path_rtypes": data['path_rtypes'],
						"path_uids": data['path_uids'],
						"table_uids": [t_item['uid'] for t_item in data['table_items']],
						"has_children": data['has_children'],
						"sev": [t_item['sev_measure'] for t_item in data['table_items']]
						}
		resource_by_uid = { item['uid'] : item for item in data['table_items'] }
		current_uid = table_data['table_uids'][table_data['row_selector']]
	else:
		table_data = {	"mode": START_MODE,
						"col_names": ["kind", "name"],
						"col_widths": lwin.get_column_widths([1/6, 5/6]),
						"table": [],
						"row_selector": 0,
						"start_y": 0,
						"path_names": [],
						"path_rtypes": [],
						"path_uids": [],
						"table_uids": [],
						"has_children": [],
						"sev": []
						}
		resource_by_uid = { "empty": None }
		current_uid = "empty"

	lwin.set_contents(**table_data)
	lwin.draw()
	rwin.draw(ftype, resource_by_uid[current_uid])

	# state that needs to be tracked
	c = 0
	ltable = []				# stack to keep track of table_start_y and row selector positions
	query_state = {"resource_by_uid": {"empty": None},	# stores last known state for query mode
					"current_uid": "empty",				# so that it can be restored when user re-enters query mode
					"table_data": {"mode": "query",
							"col_names" : ["kind", "name"],
							"col_widths" : lwin.get_column_widths([1/6, 5/6]),
							"table" : [],
							"row_selector" : 0,
							"start_y" : 0,
							"path_names" : [],
							"path_rtypes" : [],
							"path_uids" : [],
							"table_uids" : [],
							"has_children": [],
							"sev": []}
				}

	fmodes = { ord("y") : "yaml", ord("l") : "logs", ord("s") : "summary", ord("e") : "events"}
	modes = { ord("1") : "cluster", ord("2") : "app", ord("3") : "anomaly"}

	# start listening for keystrokes, and act accordingly
	while c != ord('q'):
		c = stdscr.getch()
		if c in modes:
			mode = modes[c]
			data = load(mode, twin, current_uid)
			if len(data['table_items']) > 0:
				table_data, resource_by_uid, current_uid = update(mode, table_data, data, twin, lwin, ftype, panel_side)

		elif c == ord('4'):		# query mode
			mode = "query"
			twin.draw(mode=mode, ftype=ftype, panel=panel_side)
			twin.init_load(mode)

			# draw right before left so that cursor shows up in search bar
			rwin.draw(ftype, query_state['resource_by_uid'][query_state['current_uid']])

			# draw the left window
			lwin.set_contents(**query_state['table_data'])
			lwin.draw()

			# set state variables for left window after user presses ESC
			resource_by_uid, current_uid, table_data = query_mode(stdscr, ftype, query_state)

			# save the search results state in case we come back to query mode
			query_state["resource_by_uid"] = copy.deepcopy(resource_by_uid)
			query_state["current_uid"] = copy.copy(current_uid)
			query_state["table_data"] = copy.deepcopy(table_data)

		elif c in fmodes.keys():
			ftype = fmodes[c]
			rwin.scroll_y = 0
			rwin.draw(ftype, resource_by_uid[current_uid])
			twin.draw(mode=mode, ftype=ftype, panel=panel_side)

		elif c == ord('L') :
			panel_side = "left"
			twin.draw(mode=mode, ftype=ftype, panel=panel_side)

		elif c == ord('R') :
			panel_side = "right"
			twin.draw(mode=mode, ftype=ftype, panel=panel_side)

		elif c == curses.KEY_UP:
			if panel_side == "left":
				current_uid = lwin.move_up()
				rwin.scroll_y, rwin.scroll_x = 0, 0
				rwin.draw(ftype, resource_by_uid[current_uid])
			else:
				if rwin.scroll_y > 0:
					rwin.scroll_y -= 1
					rwin.draw(ftype, resource_by_uid[current_uid])

		elif c == curses.KEY_DOWN:
			if panel_side == "left":
				current_uid = lwin.move_down()
				rwin.scroll_y, rwin.scroll_x = 0, 0
				rwin.draw(ftype, resource_by_uid[current_uid])
			else:
				if rwin.scroll_y < rwin.doc_height - rwin.panel_height:
					rwin.scroll_y += 1
					rwin.draw(ftype, resource_by_uid[current_uid])

		elif c == curses.KEY_RIGHT or c == 10:
			if panel_side == "left":
				if table_data['mode'] in ['app', 'cluster']:
					# gets the children of the current resource and other relevant info
					data = load("children", twin, current_uid, table_data["mode"])
					if len(data['table_items']) > 0:
						# save row selector and start_y for table
						ltable.append( lwin.table_start_y )
						# update and redraw
						table_data['start_y'] = 0
						rwin.scroll_y, rwin.scroll_x = 0, 0
						table_data, resource_by_uid, current_uid = update(mode, table_data, data, twin, lwin, ftype, panel_side)

		elif c == curses.KEY_LEFT:
			if panel_side == "left":
				if table_data['mode'] in ['app', 'cluster']:
					# retrieve row selector and start_y for table
					start_y = 0
					if len(ltable) != 0:
						start_y = ltable.pop()

					current_resource = load("current", twin, current_uid)
					if current_resource['rtype'] not in ['Application', 'Cluster']:
						# gets the siblings of the parent resource (including parent) and other relevant info
						data = load("parent", twin, parent_uid = table_data['path_uids'][-1], mode = table_data["mode"])
						table_data['start_y'] = start_y
						rwin.scroll_y, rwin.scroll_x = 0, 0
						table_data, resource_by_uid, current_uid = update(mode, table_data, data, twin, lwin, ftype, panel_side)


def query_mode(stdscr, ftype, query_state) -> Tuple[Dict, str, Dict]:
	"""
	Continuously captures input from user, displays in search bar, and updates left and right window with results.

	User must press [esc] to escape from this function.
	:param (_curses.window) stdscr
	:param (str) ftype
	:param (Dict) query_state: last query state
	:return: ( (Dict, str, Dict) )  state needed to render left and right windows
	"""
	curses.curs_set(1)	# show the cursor

	# returns whether a char is alphanumeric or not
	alpha_num = lambda x: 64 < c < 91 or 96 < c < 123 or 47 < c < 58

	# state variables needed to restore search results
	# resource_by_uid and current_uid are needed for going up/down search results
	# table_data is needed to render search results
	resource_by_uid = query_state['resource_by_uid']
	current_uid = query_state['current_uid']
	table_data = query_state['table_data']

	c = stdscr.getch()
	while True:
		if c == 27:		# esc
			break
		elif c == 127:	# backspace
			curses.curs_set(1)
			sb.backspace()
		elif c == 260:	# left arrow
			curses.curs_set(1)
			sb.move_left()
		elif c == 261:	# right arrow
			curses.curs_set(1)
			sb.move_right()
		elif c == 258:	# down arrow
			curses.curs_set(0)
			current_uid = lwin.move_down()
			table_data['row_selector'] = lwin.row_selector
			rwin.draw(ftype, resource_by_uid[current_uid])
		elif c == 259:	# up arrow
			curses.curs_set(0)
			current_uid = lwin.move_up()
			table_data['row_selector'] = lwin.row_selector
			rwin.draw(ftype, resource_by_uid[current_uid])
		elif c == 1:	# ctrl-a
			curses.curs_set(1)
			sb.move_to_start()
		elif c == 5:	# ctrl-e
			curses.curs_set(1)
			sb.move_to_end()
		elif c == 10:	# enter
			curses.curs_set(1)
			results = load("query", twin, query = sb.get_query())
			rows = [ [r["rtype"], r["name"]] for r in results ]

			# create dict that right window needs
			if len(results) > 0:
				resource_by_uid = { item['uid'] : item for item in results }
				current_uid = list(resource_by_uid.keys())[0]
				table_data = {"mode": "query",
							"col_names" : ["kind", "name"],
							"col_widths" : lwin.get_column_widths([1/6, 5/6]),
							"table" : rows,
							"row_selector" : 0,
							"start_y" : 0,
							"path_names" : [],
							"path_rtypes" : [],
							"path_uids" : [],
							"table_uids" : list(resource_by_uid.keys()),
							"has_children": [True] * len(results),
							"sev": [r['sev_measure'] for r in results]}

				# add additional cols if all pods in table
				is_pod = [res[0] == 'Pod' for res in table_data['table']]
				if all(is_pod):
					table_data["col_names"] = ["kind", "name", "", "ready", "restarts", "status"]
					table_data["col_widths"] = lwin.get_column_widths([1/6, 1-1/6-40/lwin.tr_text_width, 3/lwin.tr_text_width, 8/lwin.tr_text_width, 11/lwin.tr_text_width, 18/lwin.tr_text_width])
					for i, pod in enumerate(table_data['table_uids']):
						host_ip, pod_ip, ready, restarts = rwin.parse_pod_status(resource_by_uid[pod])
						ready = "-" if ready == "None" else ready
						restarts = "-" if restarts == "None" else restarts
						table_data['table'][i].extend(["", ready, restarts, resource_by_uid[pod]["sev_reason"]])

			else:
				resource_by_uid = {"empty": None}
				current_uid  = "empty"
				table_data = {"mode": "query",
							"col_names" : ["kind", "name"],
							"col_widths" : lwin.get_column_widths([1/6, 5/6]),
							"table" : [["", "No results found."]],
							"row_selector" : 0,
							"start_y" : 0,
							"path_names" : [],
							"path_rtypes" : [],
							"path_uids" : [],
							"table_uids" : ["empty"],
							"has_children": [True],
							"sev": ["0"]}

			# draw right window
			rwin.draw(ftype, resource_by_uid[current_uid])

			# update left window with search results
			lwin.set_contents(**table_data)
			lwin.draw()

		elif alpha_num(c) or c in (32, 40, 41, 45, 46, 58): # alphanumeric and { space ( ) - . : }
			curses.curs_set(1)
			sb.addch(chr(c))

		c = stdscr.getch()

	curses.curs_set(0)	# hide the cursor

	# return all the state necessary to restore the search results
	return (resource_by_uid, current_uid, table_data)

def update(mode, table_data, data, twin, lwin, ftype, panel_side):
	"""
	Update and draw left, right, and top windows based on mode and table data.
	:param mode: "app", "cluster", or "anomaly"
	:param table_data: current table
	:param data: new data to be reflected in table_data
	:param twin: top window
	:param lwin: left window
	:param ftype: "summary", "yaml", "logs", or "events"
	:param panel_side: "left" or "right"
	:return: (Dict) table_data, (Dict) resource_by_uid, (str) current_uid
	"""
	table_data["mode"] = mode
	if mode == 'app' or mode == 'cluster':
		table_data["col_names"] = ["kind", "name"]
		table_data["col_widths"] = lwin.get_column_widths([1/6, 5/6])
		table_data['row_selector'] = data['index']
		table_data['path_names'] = data['path_names']
		table_data['path_rtypes'] = data['path_rtypes']
		table_data['path_uids'] = data['path_uids']
		table_data['table'] = [[t_item['rtype'], t_item['name']] for t_item in data['table_items']]
		table_data["has_children"] = data['has_children']

	elif mode == 'anomaly':
		# each item in data["table_items"] is (skipper_uid, type, name, reason, message)
		table_data["col_names"] = ["kind", "name", "reason"]
		table_data["col_widths"] = lwin.get_column_widths([1/6, 2/3, 1/6])
		table_data['row_selector'] = 0
		table_data['table'] = [[t_item['rtype'], t_item['name'], t_item['sev_reason']] for t_item in data['table_items']]
		table_data["has_children"] = [True] * len(data['table_items'])

	table_data["table_uids"] = [t_item['uid'] for t_item in data['table_items']]
	table_data["sev"] = [t_item['sev_measure'] for t_item in data['table_items']]
	resource_by_uid = {item['uid']: item for item in data['table_items']}

	# add additional cols if all pods in table
	is_pod = [res[0] == 'Pod' for res in table_data['table']]
	if all(is_pod):
		table_data["col_names"] = ["kind", "name", "", "ready", "restarts", "status"]
		table_data["col_widths"] = lwin.get_column_widths([1/6, 1-1/6-40/lwin.tr_text_width, 3/lwin.tr_text_width, 8/lwin.tr_text_width, 11/lwin.tr_text_width, 18/lwin.tr_text_width])
		for i, pod in enumerate(table_data['table_uids']):
			host_ip, pod_ip, ready, restarts = rwin.parse_pod_status(resource_by_uid[pod])
			ready =  "-" if ready == "None" else ready
			restarts = "-" if restarts == "None" else restarts
			table_data['table'][i] = ["Pod", resource_by_uid[pod]['name'], "", ready, restarts, resource_by_uid[pod]['sev_reason']]

	current_uid = table_data['table_uids'][table_data['row_selector']]
	twin.draw(mode=mode, ftype=ftype, panel=panel_side)
	twin.init_load(mode)
	lwin.set_contents(*table_data.values())
	lwin.draw()
	rwin.draw(ftype, resource_by_uid[current_uid])
	return table_data, resource_by_uid, current_uid

def load(request_type, twin, current_uid = None, mode = None, parent_uid =  None, query = None, uid  = None):
	"""
	Start loading, make request and wait for response, stop loading.
	:return data from response
	"""
	twin.start_loading()
	if request_type == "cluster":
		data = requests.get('http://127.0.0.1:5000/mode/cluster/switch/{}'.format(current_uid)).json()
	elif request_type == "app":
		data = requests.get('http://127.0.0.1:5000/mode/app/switch/{}'.format(current_uid)).json()
	elif request_type == "anomaly":
		data = requests.get('http://127.0.0.1:5000/errors').json()
	elif request_type == "children":
		data = requests.get('http://127.0.0.1:5000/mode/{}/{}'.format(mode, current_uid)).json()
	elif request_type == "current":
		data = requests.get('http://127.0.0.1:5000/resource/{}'.format(current_uid)).json()['data']
	elif request_type == "parent":
		data = requests.get('http://127.0.0.1:5000/mode/{}/switch/{}'.format(mode, parent_uid)).json()
	elif request_type == "query":
		data = requests.get("http://127.0.0.1:5000/search/" + query).json()["results"]
	elif request_type == "sort":
		data = requests.get('http://127.0.0.1:5000/resource/{}'.format(uid)).json()['data']
	twin.stop_loading()
	return data

def main():
	curses.wrapper(run_skipper)

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		sys.exit(0)
