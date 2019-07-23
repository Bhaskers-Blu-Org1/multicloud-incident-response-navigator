import curses, requests, datetime, pytz, json
from dateutil.parser import parse
from tabulate import tabulate

INDENT_AMT = 4 # horizontal indent amount

status = ""


headers=["Type", "Reason", "Age", "From", "Message"]

def draw(ftype, win, panel_height, panel_width, top_height, resource_data):
	""" 
	chooses whether to draw summary, yaml, or logs based on keybinding
	:param ftype: yaml / logs / summary
	:param win: right panel
	:param panel_height: height of right panel
	:param panel_width: width of right panel
	:param top_height: right panel starting y
	:resource data: all info relevant to resource
	:return:
	"""
	if ftype == "yaml":
		draw_yaml(win, panel_height, panel_width, top_height, resource_data)
	elif ftype == "summary":
		draw_summary(win, panel_height, panel_width, top_height, resource_data)
	elif ftype == "logs":
		draw_logs(win, panel_height, panel_width, top_height, resource_data)
	elif ftype == "events":
		draw_events(win, panel_height, panel_width, top_height, resource_data)

def draw_yaml(win, panel_height, panel_width, top_height, resource_data):
	""" 
	draws the first lines of yaml that fits, TODO: also get them for custom resources and namespaces
	:param win: right panel
	:param panel_height: height of right panel
	:param panel_width: width of right panel
	:param top_height: right panel starting y
	:resource data: all info relevant to resource
	:return:
	"""
	win.erase()
	win.border(curses.ACS_VLINE, " ", " ", " ", " ", " ", " ", " ")
	rtype, rname = resource_data['rtype'], resource_data['name']
	top_banner = win.derwin(3, panel_width, 0, 0) # window.derwin(nlines (optional), ncols (optional), begin_y, begin_x)
	top_banner.addstr(1, INDENT_AMT, "Yaml: " + rname, curses.A_BOLD)

	if resource_data["rtype"] not in ["Namespace", "Cluster", "Application", "Deployable"]:
		yaml = requests.get('http://127.0.0.1:5000/resource/{}/{}'.format(resource_data["cluster"]+'_'+resource_data["uid"].split('_')[-1], "yaml")).json()["yaml"].split('\n')
		y = 3
		for i in range (min(panel_height-3, len(yaml))):
			win.addstr(y, INDENT_AMT, yaml[i])
			y += 1
	else:
		win.addstr(3, INDENT_AMT, "Yaml not found")
	win.refresh()

def draw_logs(win, panel_height, panel_width, top_height, resource_data):
	""" 
	draws the first lines of logs that fit, also tells user about the nonexistence of logs for resources other than pods"
	:param win: right panel
	:param panel_height: height of right panel
	:param panel_width: width of right panel
	:param top_height: right panel starting y
	:resource data: all info relevant to resource
	:return:
	"""
	win.erase()
	win.border(curses.ACS_VLINE, " ", " ", " ", " ", " ", " ", " ")
	rtype, rname = resource_data['rtype'], resource_data['name']
	top_banner = win.derwin(3, panel_width, 0, 0) # window.derwin(nlines (optional), ncols (optional), begin_y, begin_x)
	top_banner.addstr(1, INDENT_AMT, "Logs: " + rname, curses.A_BOLD)

	if resource_data["rtype"] in ["Pod"]:
		logs = requests.get('http://127.0.0.1:5000/resource/{}/{}'.format(resource_data["cluster"]+'_'+resource_data["uid"].split('_')[-1], "logs")).json()["logs"].split('\n')
		y = 3
		for i in range (min(panel_height-3, len(logs))):
			draw_str(win, 3, INDENT_AMT, logs[i], panel_width-INDENT_AMT)
			y += 1
	else:
		win.addstr(3, INDENT_AMT, "Logs only exist for pods")
	win.refresh()

def draw_events(win, panel_height, panel_width, top_height, resource_data):
	"""
	queries database, formats events with tabulate and then draws it
	:param y: y coord to start in
	:param win: window to draw in
	:param resource_data: all info related to resource of interest
	:param width: width allowed before wrapping
	:return:
	"""
	win.erase()
	win.border(curses.ACS_VLINE, " ", " ", " ", " ", " ", " ", " ")
	rtype, rname = resource_data['rtype'], resource_data['name']
	top_banner = win.derwin(3, panel_width, 0, 0) # window.derwin(nlines (optional), ncols (optional), begin_y, begin_x)
	top_banner.addstr(1, INDENT_AMT, "Events: " + rname, curses.A_BOLD)

	if rtype not in ["Cluster"]:
		events_table = requests.get('http://127.0.0.1:5000/resource/{}/{}'.format(resource_data["cluster"]+'_'+resource_data["uid"].split('_')[-1], "events")).json()["events"]
		if events_table == "Events not found":
			draw_str(win, 3, INDENT_AMT, events_table, panel_width-2*INDENT_AMT)
		else:
			lines = tabulate(events_table, headers=headers).split('\n')
			y = 3
			for line in lines:
				y = draw_str(win, y, INDENT_AMT, line, panel_width-2*INDENT_AMT)
	else:
		win.addstr(3, INDENT_AMT, "Events not found")
	win.refresh()

	# bottom = win.derwin(y+3, INDENT_AMT) # starting at y+3 due to height of top banner
	# bottom.addstr(1, 0, "Events:")
	# y += draw_str(bottom, 2, 0, tabulate(events_table, headers=headers), width-2*INDENT_AMT)
	# temporary solution for formatting events, does not take care of text wrapping
	# need to check source column
	# return y

def draw_summary(win, length, width, top_height, resource_data):
	"""
	refreshes and populates summary pane with info based on resource
	creates top, left, and right derwins for top banner and columns
	:param resource_data: all data related to the current resource to be displayed
	:return:
	"""
	win.erase()
	win.border(curses.ACS_VLINE, " ", " ", " ", " ", " ", " ", " ")	# left border

	if resource_data == None:
		win.refresh()
		return

	rtype, rname = resource_data['rtype'], resource_data['name']
	resource_data["status"] = status

	if resource_data["created_at"] != "None":
		resource_data["age"] = calc_age(datetime.datetime.utcnow() - parse(resource_data["created_at"]))
	else:
		resource_data["age"] = "None"

	resource_data["uid"]  = resource_data["uid"].split("_")[-1]

	# top banner displaying resource type and name
	top_banner = win.derwin(3, width, 0, 0) # window.derwin(nlines (optional), ncols (optional), begin_y, begin_x)
	top_banner.addstr(1, INDENT_AMT, rtype + ": " + rname, curses.A_BOLD)
	# top_banner.addstr(1, INDENT_AMT+width//2, "Name: " + rname, curses.A_BOLD)
	# top_banner.hline(4, 1, curses.ACS_HLINE, 2*width-2)

	info_length = length-3
	left = win.derwin(info_length, width//2-INDENT_AMT, 3, INDENT_AMT)
	right = win.derwin(info_length, width//2-2*INDENT_AMT, 3, width//2+INDENT_AMT)

	if rtype == "Application":
		y = draw_app(win, left, right, length, width, resource_data)
	elif rtype == "Cluster":
		resource_data["status"] = ""
		y = draw_cluster(win, left, right, length, width, resource_data)
	elif rtype == "Namespace":
		resource_data["status"] = ""
		y = draw_ns(win, left, right, length, width, resource_data)
	elif rtype in ["Deployment", "Deployable", "StatefulSet", "ReplicaSet", "DaemonSet"]:
		resource_data["status"] = ""
		y = draw_work(win, left, right, length, width, resource_data)
	elif rtype == "Pod":
		y = draw_pod(win, left, right, length, width, resource_data)
	elif rtype == "Service":
		y = draw_service(win, left, right, length, width, resource_data)
	else:
		y = 0

	y += 3 # to account for top banner length
	draw_related_resources(win, y + 5, {})
	# win.refresh(0, 0, top_height, width, top_height+length, 2*width)
	win.refresh()

def draw_related_resources(win, y, resources):
	"""
	will list all related resources
	:param win: window to draw in
	:param y: row to start on
	:param resources: dictionary of related resources
	:return:
	"""
	win.addstr(y, INDENT_AMT, "Related Resources", curses.A_BOLD)
	# to be filled with other related resources

def draw_service(win, left, right, length, width, resource_data):
	"""
	fills in left and right windows will info relevant to service
	:param win: window to draw in
	:param left: left column window
	:param right: right column window
	:param length: panel length
	:param width: panel width for formatting
	:resource data: all info relevant to service
	:return: y coordinate to start drawing related resources on
	"""
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		selector = info["selector"] if info.get("selector") and (info.get("selector") != "None") else None
		ports = info["ports"] if info.get("ports") and (info.get("ports") != "None") else None
		# labels, selector, ports = info.get("labels"), info.get("selector"), info.get("ports")
	else:
		labels, selector, ports = None, None, None

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + resource_data["status"]]
	y = iterate_info(win, left, right, lfields, rfields, width)

	lefty = righty = y
	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)
	if selector is not None:
		lefty = draw_pairs(left, lefty, "Selector:", width//2-INDENT_AMT, selector)

	if ports is not None:
		# draw_str(right, righty, INDENT_AMT, str(ports[0]), width//2-2*INDENT_AMT)
		righty = draw_pairs(right, righty, "Ports: ", width//2-2*INDENT_AMT, ports[0])

	return max(lefty,righty)

def draw_work(win, left, right, length, width, resource_data):
	""" 
	fills in left and right windows will info relevant to Deployment / Deployable / StatefulSet / ReplicaSet / DaemonSet
	:param win: window to draw in
	:param left: left column window
	:param right: right column window
	:param length: panel length
	:param width: panel width for formatting
	:resource data: all info relevant to Deployment / Deployable / StatefulSet / ReplicaSet / DaemonSet
	:return: y coordinate to start drawing related resources on
	"""
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		status = info["status"] if info.get("status") and (info.get("status") != "None") else None
		available = info["available"]
		updated = info["updated" ]
		ready_reps = info["ready_reps"]
	else:
		labels, status, available, updated, ready_reps = "None", "None", "None", "None", "None"

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"]]
	if resource_data['rtype'] not in ["Deployable", "StatefulSet"]:
		rfields.extend(["Ready: " + ready_reps, "Available: " + available, "Up-to-date: " + updated])
	y = iterate_info(win, left, right, lfields, rfields, width)

	if labels is not None:
		y = draw_pairs(left, y, "Labels:", width//2-INDENT_AMT, labels)
	if status is not None:
		y = draw_pairs(left, y, "Status:", width//2-INDENT_AMT, status)
	# win.addstr(y, INDENT_AMT, "y count: "+str(y))
	return y

def draw_ns(win, left, right, length, width, resource_data):
	"""
	fills in left and right windows will info relevant to namespace
	:param win: window to draw in
	:param left: left column window
	:param right: right column window
	:param length: panel length
	:param width: panel width for formatting
	:resource data: all info relevant to namespace
	:return: y coordinate to start drawing related resources on
	"""
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		status = info["status"] if info.get("status") and (info.get("status") != "None") else None
		k8s_uid = info["k8s_uid"] if info.get("k8s_uid") and (info.get("k8s_uid") != "None") else None
	else:
		status = None

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + k8s_uid]
	rfields = ["Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + str(status)]

	return iterate_info(win, left, right, lfields, rfields, width)

# Further needed info: labels, status, age, deployables, events)
def draw_app(win, left, right, length, width, resource_data):
	"""
	fills in left and right windows will info relevant to app
	:param win: window to draw in
	:param left: left column window
	:param right: right column window
	:param length: panel length
	:param width: panel width for formatting
	:resource data: all info relevant to app
	:return: y coordinate to start drawing related resources on
	"""
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		status = info["status"] if info.get("status") and (info.get("status") != "None") else None
	else:
		labels, status = None, None

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"]]
	rfields = ["Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + str(status)]

	lefty = iterate_info(win, left, right, lfields, rfields, width)
	righty = lefty

	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-2*INDENT_AMT, labels)

	# righty = draw_pairs(right, righty, "Deployables: ", width//2-2*INDENT_AMT, info["deployables"].split(","))

	return max(lefty,righty)

def draw_pod(win, left, right, length, width, resource_data):
	"""
	fills in left and right windows will info relevant to pod
	:param win: window to draw in
	:param left: left column window
	:param right: right column window
	:param length: panel length
	:param width: panel width for formatting
	:resource data: all info relevant to pod
	:return: y coordinate to start drawing related resources on
	"""
	if resource_data["info"] != "None":
		info = json.loads(resource_data["info"])
		labels = info["labels"] if info.get("labels") and (info.get("labels") != "None") else None
		owner_refs = info["owner_refs"][0] if info.get("owner_refs") and (info.get("owner_refs") != "None") else None
		host_ip = info["host_ip"] if info.get("host_ip") and (info.get("host_ip") != None) else "None"
		phase = info["phase"] if info.get("phase") and (info.get("phase") != None) else "None"
		pod_ip = info["pod_ip"] if info.get("pod_ip") and (info.get("pod_ip") != None) else "None"
		ready = info["ready"] if info.get("ready") and (info.get("ready") != None) else "None"
		restarts = info["restarts"] if info.get("restarts") and (info.get("restarts") != None) else "None"
		container_count = info["container_count"] if info.get("container_count") and (info.get("container_count") != None) else "None"
	else:
		labels, owner_refs, host_ip, phase, pod_ip, ready, restarts, container_count = None, None, "None", "None", "None", "None", "None", "None"

	lfields = ["Cluster: " + resource_data["cluster"], "Namespace: " + resource_data["namespace"], "UID: " + resource_data["uid"], "PodIP: " + pod_ip, "Node/HostIP: " + host_ip]
	rfields = ["Ready: " + ready, "Restarts: " + restarts, "Age: " + resource_data["age"], "Created: " + resource_data["created_at"], "Last updated: "+resource_data["last_updated"], "Status: "  + phase]

	lefty = iterate_info(win, left, right, lfields, rfields, width)
	righty = lefty

	if labels is not None:
		lefty = draw_pairs(left, lefty, "Labels:", width//2-INDENT_AMT, labels)

	if owner_refs is not None:
		righty = draw_pairs(right, righty, "Owner References:", width//2-2*INDENT_AMT, owner_refs)

	y = max(lefty,righty)
	return y


def draw_cluster(win, left, right , length, width, resource_data):
	"""
	fills in left and right windows will info relevant to cluster
	:param win: window to draw in
	:param left: left column window
	:param right: right column window
	:param length: panel length
	:param width: panel width for formatting
	:resource data: all info relevant to cluster
	:return: y coordinate to start drawing related resources on
	"""
	lines = [ "Welcome to Skipper, a cross-cluster terminal application", \
			  "We will be loading in more info about your cluster in the future", \
			  "But for now please scroll and arrow right to view more resources"
				]
	lefty = 3
	for line in lines:
		lefty = draw_str(win, lefty, INDENT_AMT, line, width)+1
	return lefty

def calc_age(time):
	"""
	turns datetime or timedelta object into an age string
	:param time: date object
	:return: string of age followed by 1 char unit of time
	"""
	if time.days == 0:
		hours = time.seconds // 3600
		if hours == 0:
			minutes = time.seconds // 60
			if minutes == 0:
				return str(time.seconds)
			return str(minutes)+"m"
		return str(hours)+"h"
	return str(time.days)+"d"

def iterate_info(win, left, right, lfields, rfields, width):
	"""
	draws lines of information for left and right columns
	:param win: window to draw in
	:param left: left column window
	:param right: right column window
	:param lfields: list of fields/ info to fill in for left column
	:param rfields: list of fields/ info to fill in for right column
	:param width: width of entire right panel
	:return: y coordinate that the columns end on (whichever ends later)
	"""
	lefty, righty = 0, 0
	for string in lfields:
	   lefty = draw_str(left, lefty, 0, string, width//2-2*INDENT_AMT)

	for string in rfields:
	   righty = draw_str(right, righty, 0, string, width//2-2*INDENT_AMT)

	return max(lefty, righty)

def iterate_indented_pairs(win, start_y, start_x, pairs, alloted_width, indent = False):
	"""
	draws and wraps pairs of information, where pairs are indented one from title
	:param start_y: y coord to start in
	:param start_x: x coord to start in
	:param pairs: dict of information to draw
	:param alloted_width: width of allowed  before wrapping
	:param indent (optional): whether to indent the pairs
	:return: y coordinate that the pairs end on
	"""
	for pair in pairs:
		pair = pair+"="+str(pairs[pair])
		if (len(pair) > alloted_width-(INDENT_AMT*indent)):
			lines = [ pair[i:i + alloted_width-INDENT_AMT*indent] for i in range(0, len(pair), alloted_width-INDENT_AMT*indent) ]
			win.addstr(start_y, start_x+(INDENT_AMT*indent), lines[0])
			lines = lines[1:]
			start_y += 1
			for line in lines:
				# win.addstr(start_y, start_x+(INDENT_AMT*indent), line)
				win.addstr(start_y, start_x+(INDENT_AMT*indent), line)
				start_y += 1
		else:
			win.addstr(start_y, start_x+(INDENT_AMT*indent), pair)
			start_y += 1
	return start_y

def draw_str(win, y, x, string, maxw):
	"""
	draws and wraps string
	:param win: window to draw in
	:param y: y coord to start in
	:param x: x coord to start in
	:param string: string to be drawn
	:param maxw: width of allowed before wrapping
	:return: y coordinate that the string ends on
	"""
	if (len(string) > maxw):
		lines = [ string[i:i + maxw] for i in range(0, len(string), maxw) ]
		win.addstr(y, x, lines[0])
		lines = lines[1:]
		y += 1
		for line in lines:
			win.addstr(y, x, line)
			y += 1
	else:
		win.addstr(y, x, string)
		y += 1
	return y

def draw_pairs(win, y, name, width, pairs):
	"""
	draws title and info (which are pairs)
	:param win: window to draw in
	:param y: y coord to start in
	:param name: type/name/title of pairs to be drawn
	:param width: width allowed before wrapping
	:param pairs: dict of pairs to be drawn
	:return: y coordinate that the string ends on
	"""
	y = draw_str(win, y+1, 0, name, width)
	y = iterate_indented_pairs(win, y, 0, pairs, width, indent = True)
	return y
