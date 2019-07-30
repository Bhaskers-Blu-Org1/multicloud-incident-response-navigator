import curses
import skipper_helpers as shs
import curses_helpers as chs
import left_window as lwin
import top_window as twin
import search_bar as sb
import right_window as rwin
import sys, requests
from typing import Dict, Tuple
import copy

def run_skipper(stdscr):
	"""
	Runs the Skipper interactive terminal application.

	Arguments: (_curses.window) stdscr
					Automatically passed in by curses.wrapper function.
					A _curses.window obj that represents the entire screen.
	Returns:	None
	"""

	START_MODE = "cluster"	# possible modes include app, cluster, query, anomaly
	START_FTYPE = "summary"
	START_PANEL = "left"
	# initialize stdscr (standard screen)
	stdscr = chs.initialize_curses()

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
	height, width = stdscr.getmaxyx()
	twin.init_win(stdscr, len(shs.figlet_lines()) + 3, width, 0,0)	# height, width, y, x
	twin.draw(mode=mode, ftype=ftype, panel=panel_side)
	top_height, top_width = twin.window.getmaxyx()
	panel_height = height-top_height
	panel_width = width//2

	# initialize and draw windows
	lwin.init_win(stdscr, height=panel_height, width=width//2, y=top_height, x=0)
	rwin.init(stdscr, panel_height, panel_width, top_height)

	if len(data['table_items']) > 0:
		table_data = {	"mode": START_MODE,
						"col_names": ["kind", "name"],
						"col_widths": [20, 60],
						"table": [[t_item['rtype'], t_item['name']] for t_item in data['table_items']],
						"row_selector": data['index'],
						"start_y": 0,
						"path_names": data['path_names'],
						"path_rtypes": data['path_rtypes'],
						"path_uids": data['path_uids'],
						"table_uids": [t_item['uid'] for t_item in data['table_items']]
						}
		resource_by_uid = { item['uid'] : item for item in data['table_items'] }
		current_uid = table_data['table_uids'][table_data['row_selector']]
		lwin.set_contents(*table_data.values())
	ftype = START_FTYPE
	lwin.draw()
	rwin.draw(ftype, resource_by_uid[current_uid])

	# state that needs to be tracked
	c = 0
	ltable = []				# stack to keep track of table_start_y and row selector positions
	query_state = {"resource_by_uid": {"empty": None},	# stores last known state for query mode
					"current_uid": "empty",				# so that it can be restored when user re-enters query mode
					"table_data": {"mode": "query",
							"col_names" : ["kind", "name"],
							"col_widths" : [20, 60],
							"table" : [],
							"row_selector" : 0,
							"start_y" : 0,
							"path_names" : [],
							"path_rtypes" : [],
							"path_uids" : [],
							"table_uids" : []}
				}

	modes = { ord("y") : "yaml", ord("l") : "logs", ord("s") : "summary", ord("e") : "events"}
	# start listening for keystrokes, and act accordingly
	while c != ord('q'):
		c = stdscr.getch()

		if c == ord('1'):		# cluster mode
			data = requests.get('http://127.0.0.1:5000/mode/cluster/switch/{}'.format(current_uid)).json()
			if len(data['table_items']) > 0:
				table_data, resource_by_uid, current_uid = update("cluster", table_data, data, twin, lwin, ftype, panel_side)
			mode = "cluster"
		elif c == ord('2'):		# app mode
			data = requests.get('http://127.0.0.1:5000/mode/app/switch/{}'.format(current_uid)).json()
			if len(data['table_items']) > 0:
				table_data, resource_by_uid, current_uid = update("app", table_data, data, twin, lwin, ftype, panel_side)
			mode = "app"
		elif c == ord('3'):		# anomaly mode
			data = requests.get('http://127.0.0.1:5000/errors').json()
			if len(data["table_items"]) > 0:
				table_data, resource_by_uid, current_uid = update("anomaly", table_data, data, twin, lwin, ftype, panel_side)
			mode = "anomaly"
		elif c == ord('4'):		# query mode
			mode = "query"
			twin.draw(mode=mode, ftype=ftype, panel=panel_side)
			table_data["mode"] = mode

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

		elif c in modes.keys():
			ftype = modes[c]
			rwin.scroll_y = 0
			rwin.draw(ftype, resource_by_uid[current_uid])
			twin.draw(mode=mode, ftype=ftype, panel=panel_side)

		elif c == ord('L') :
			panel_side = "left"
			twin.draw(mode=mode, ftype=ftype, panel=panel_side)

		elif c ==  ord('R') :
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
					parent_uid = current_uid
					# gets the children of the current resource and other relevant info
					data = requests.get('http://127.0.0.1:5000/mode/{}/{}'.format(table_data["mode"],current_uid)).json()
					if len(data['table_items']) > 0:
						# save row selector and start_y for table
						ltable.append( lwin.table_start_y )
						# update and redraw
						table_data['start_y'] = 0
						rwin.scroll_y, rwin.scroll_x = 0, 0
						table_data, resource_by_uid, current_uid = update(table_data["mode"], table_data, data, twin, lwin, ftype, panel_side)

		elif c == curses.KEY_LEFT:
			if panel_side == "left":
				if table_data['mode'] in ['app', 'cluster']:
					# retrieve row selector and start_y for table
					start_y = 0
					if len(ltable) != 0:
						start_y = ltable.pop()

					current_resource = requests.get('http://127.0.0.1:5000/resource/{}'.format(current_uid)).json()['data']
					if current_resource['rtype'] not in ['Application', 'Cluster']:
						# gets the siblings of the parent resource (including parent) and other relevant info
						parent_uid = table_data['path_uids'][-1]
						data = requests.get('http://127.0.0.1:5000/mode/{}/switch/{}'.format(table_data["mode"], parent_uid)).json()
						table_data['start_y'] = start_y
						rwin.scroll_y, rwin.scroll_x = 0, 0
						table_data, resource_by_uid, current_uid = update(table_data["mode"], table_data, data, twin, lwin, ftype, panel_side)


def query_mode(stdscr, ftype, query_state) -> Tuple[Dict, str, Dict]:
	"""
	Continuously captures input from user, displays in search bar, and updates left and right window with results.

	User must press [esc] to escape from this function.
	Arguments: 	(_curses.window) stdscr
	Returns:	( (dict, str, dict) )  state needed to render left and right windows
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
			query = sb.get_query()
			results = requests.get("http://127.0.0.1:5000/search/" + query).json()["results"]
			rows = [ [r["rtype"], r["name"]] for r in results ]

			# create dict that right window needs
			if len(results) > 0:
				resource_by_uid = { item['uid'] : item for item in results }
				current_uid = list(resource_by_uid.keys())[0]
				table_data = {"mode": "query",
							"col_names" : ["kind", "name"],
							"col_widths" : [20, 60],
							"table" : rows,
							"row_selector" : 0,
							"start_y" : 0,
							"path_names" : [],
							"path_rtypes" : [],
							"path_uids" : [],
							"table_uids" : list(resource_by_uid.keys())}
			else:
				resource_by_uid = {"empty": None}
				current_uid  = "empty"
				table_data = {"mode": "query",
							"col_names" : ["kind", "name"],
							"col_widths" : [20, 60],
							"table" : [["", "No results found."]],
							"row_selector" : 0,
							"start_y" : 0,
							"path_names" : [],
							"path_rtypes" : [],
							"path_uids" : [],
							"table_uids" : ["empty"]}

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
	table_data["mode"] = mode
	if mode == 'app' or mode == 'cluster':
		table_data["col_names"] = ["kind", "name"]
		table_data["col_widths"] = [20, 60]
		table_data['row_selector'] = data['index']
		table_data['path_names'] = data['path_names']
		table_data['path_rtypes'] = data['path_rtypes']
		table_data['path_uids'] = data['path_uids']
		table_data['table'] = [[t_item['rtype'], t_item['name']] for t_item in data['table_items']]
		table_data["table_uids"] = [t_item['uid'] for t_item in data['table_items']]
		resource_by_uid = {item['uid']: item for item in data['table_items']}
	elif mode == 'anomaly':
		# each item in data["table_items"] is (skipper_uid, type, name, reason, message)
		table_data["col_names"] = ["kind", "name", "reason"]
		table_data["col_widths"] = [15, 60, 10]
		table_data['row_selector'] = 0
		table_data['table'] = [[t_item[1], t_item[2], t_item[3]] for t_item in data['table_items']]
		table_data["table_uids"] = [t_item[0] for t_item in data['table_items']]
		resource_by_uid = {item[0]: requests.get('http://127.0.0.1:5000/resource/{}'.format(item[0])).json()['data'] for item in data['table_items']}

	current_uid = table_data['table_uids'][table_data['row_selector']]
	twin.draw(mode=mode, ftype=ftype, panel=panel_side)
	lwin.set_contents(*table_data.values())
	lwin.draw()
	rwin.draw(ftype, resource_by_uid[current_uid])
	return table_data, resource_by_uid, current_uid

def main():
	curses.wrapper(run_skipper)

if __name__ == "__main__":
	try:
		main()
	except KeyboardInterrupt:
		sys.exit(0)
