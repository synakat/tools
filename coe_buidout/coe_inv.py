#!/usr/bin/python

import csv
import sys
import pprint


header = """
################################################################################################################
# Generated COE inventory using  coe_inv.py against a csv (MSDOS) Excel export
################################################################################################################


# For a full set of options and values see:
# https://raw.githubusercontent.com/openshift/openshift-ansible/master/inventory/byo/hosts.origin.example
# ../openshift-ansible/inventory/byo/hosts.origin.example
#
# When adding labels to your nodes please follow the guidance in this document:
# https://wiki.cisco.com/pages/viewpage.action?pageId=64776674
################################################################################################################


[all:vars]
cluster_timezone=UTC

### We are separating the process of upgrading cluster node operating systems from upgrading Openshift
### with this, we will no longer need to reboot the nodes after the pre-installation step
### this action is selectable now, with the following option. Normally now set to false.
reboot_after_preinstall=false
reboot_timeout_after_preinstall=120
reboot_pause_after_preinstall=10"""

para1="""
### We are separating the process of upgrading cluster node operating systems from upgrading Openshift
### with this, we will no longer need to run an yum upgrade all in the pre-installation step
### this action is selectable now, with the following option. Normally now set to false.
yum_upgrade_during_preinstall=false
"""
para2="""
#values may be a comma separated list to specify additional registries
#the deployers registry (eg <DEPLOYER-IP>:5000) must be the first entry in this list
"""

para3="""
### Apply additional performance tuning via custom tuned profile for specific use cases such as:
### - Data Plane (dp), Control Plane (cp), etc.
#
# coe_tuned_profile controls what tuned profile to apply after the COE is deployed and has the following
# format:
#        coe_tuned_profile=<profile_name>
# where profile_name can be set to DataPlane, ControlPlane, etc. Please note that these tuned profiles
# are mutually exclusive and only one of them MUST be specified.
#
# By default, coe_tuned_profile is not set and thus COE tuned profile functionality is disabled.
# Currently only "DataPlane" profile is supported and can be enabled by uncommenting the following line.
coe_tuned_profile=DataPlane



# Create an OSEv3 group that contains the masters and nodes groups
[OSEv3:children]
masters
nodes
etcd
lb
gluster
new_nodes


# Set variables common for all OSEv3 hosts
[OSEv3:vars]
ansible_ssh_user=root
ansible_become=true
debug_level=2
deployment_type=origin
openshift_image_tag=v3.7.2
openshift_install_examples=false
openshift_master_cluster_method=native
openshift_pkg_version=-3.7.2
openshift_release=v3.7

# increase max number of inflight requests
openshift_master_max_requests_inflight=1000

# Change the service public host range on hosts should you need it
#    default range is 30000-32767
openshift_node_port_range=9000-9999
"""

minions_para ="""
[minions:vars]
#reboot_timeout=<TIMEOUT IN SECONDS>  ### SET THIS and remove this comment
pv_device=sdb
pv_part=1
"""
para4="""
#host group for nodes
[nodes:children]
masters
minions
gluster

[nodes:vars]
pv_device=sdb
pv_part=1

## The [new_masters] group is used when performing a scaleup process.
## Ansible will expect this block to exist in the inventory EVEN if it is empty.
## DO NOT comment or remove [new_masters], but it can be an empty group
[new_masters]


## The [new_masters:vars] group is used when performing a scaleup process.
## Ansible will expect this block to exist in the inventory EVEN if it is empty.
## DO NOT comment or remove [new_masters:vars], but it can be an empty group
[new_masters:vars]


## The [new_minions] group is used when performing a scaleup process.
## Ansible will expect this block to exist in the inventory EVEN if it is empty.
## DO NOT comment or remove [new_minions], but it can be an empty group
[new_minions]
## The [new_minions:vars] group is used when performing a scaleup process.
## Ansible will expect this block to exist in the inventory EVEN if it is empty.
## DO NOT comment or remove [new_minions:vars], but it can be an empty group
[new_minions:vars]


## The [new_nodes:children] group is used when performing a scaleup process.
## Ansible will expect this block to exist in the inventory ALWAYS.
## DO NOT comment or remove [new_nodes:children], new_master or new_minions
[new_nodes:children]
new_masters
new_minions


## The [new_nodes:vars] group is used when performing a scaleup process.
## Ansible will expect this block to exist in the inventory EVEN if it is empty.
## DO NOT comment or remove [new_nodes:vars], but it can be an empty group
[new_nodes:vars]
#pv_device=<DISK>  ### describe an empty disk device  ### SET THIS and remove this comment
#pv_part=<PART>    ### and partition for docker caching ### SET THIS and remove this comment
pv_device=sdb
pv_part=1


#host group for nfs servers
#[nfs]
#<IPADDR> ansible_ssh_host=<IPADDR> openshift_ip=<IPADDR> openshift_public_ip=<IPADDR> openshift_public_hostname=<IPADDR> openshift_hostname=<IPADDR>  ### SET THIS and remove this comment

#[nfs:vars]
#number_of_pvs=<NUM>  ### SET THIS and remove this comment


[etcd:children]
masters
new_masters

[etcd:vars]
"""
def main():

	if len(sys.argv) < 5:
		usage_msg()
		return
		
	pr = pprint.PrettyPrinter(indent=3)
	inventory_ss = sys.argv[1]
	pod = sys.argv[2]
	vmr = sys.argv[3]
	mode = sys.argv[4]
	
	with open(inventory_ss, 'rb') as inv:
	
		inv_ = csv.DictReader(inv, dialect='excel', delimiter=',')
		pod_result = filter(lambda x: x["POD"] == pod , inv_)
		if len(pod_result) == 0:
			print("ERR  POD{0} data not found,check csv file ... exiting".format(pod))
			return
		
		docker_regs = filter(lambda x: x["Type"] == "ch-drg", pod_result)
		vmr_result = filter(lambda x: discern_vmr(x["Description\xff"], vmr), pod_result)
		if len(pod_result) == 0:
			print("ERR  POD{0} VMR {1} data not found,check csv file ... exiting".format(pod,vmr))
			return
		try:
			dpl = filter(lambda x: x["Type"] == "ci-dpl", vmr_result)
			yum_repo = dpl[0]["IPv4"]
			deployer = dpl[0]
		except:
			print "# WARNING  deployer not detected for this POD, check for typos and format correctness or edit inventory manually"
			pass
		try:	
			vips = filter(lambda x: x["Type"] == "ci-klv",vmr_result)
			pod_vip =  vips[0]["IPv4"]
			pod_eth = vips[0]["Interface\xff"]
		except:
			print "# WARNING  minion  vips not detected for this POD, check for typos and format correctness or edit inventory manually"
			pass
	
		minions = filter(lambda x: x["Type"] == "ci-knd",vmr_result)
		masters = filter(lambda x: x["Type"] == "ci-kmr",vmr_result)
		routersets = filter(lambda x: x["Type"] == "ci-knv",vmr_result)
		lbs = filter(lambda x: x["Type"] == "ci-klb",vmr_result)
		#pr.pprint(vips)
	
	if mode == "--info":
		print "POD information ----------------------------------------------------------------------------------------------" 
		map(print_info,  pod_result)
		print"VMR information ----------------------------------------------------------------------------------------------" 
		map(print_info,  vmr_result)
		
		return 
		
	print header
	print("openshift_master_default_subdomain={0}".format("ladc.ca.charter.com"))
	print("openshift_master_cluster_public_hostname={0}".format("ladcca-ci-klv-1101.ladc.ca.charter.com"))
	print
	print("keepalived_vip={0}".format(pod_vip))
	print("keepalived_interface={0}".format(pod_eth))
	print("keepalived_vrrpid={0}".format("15"))
	print para1
	print("yumrepo_url=http://{0}/centos/7/".format(yum_repo))
	print para2	
	print("openshift_docker_additional_registries={0},{1}".format("47.3.0.22:5000","47.3.5.133:5000"))
	print("openshift_docker_insecure_registries={0},{1}".format("47.3.0.22:5000","47.3.5.133:5000"))


	print "openshift_docker_blocked_registries=docker.io"

	print "#optional list of ntp server(s) accessible to all cluster nodes (with alternative examples)"
	print "#setting a value overrides the default upstream ntp server list"
	print "##ntp_servers=[\"<NTP_SERVER1>\",\"<NTP_SERVER2>\",\"<NTP_SERVER3>\"]"
	print "ntp_servers=[\"71.10.216.7\",\"71.10.216.8\"]"
	print para3
	print "openshift_disable_check=disk_availability,docker_storage,docker_image_availability,package_availability"	
	_rscount = 1
	for row in routersets:
		print("routerset{0}=[ \"dp{0}\", \"network=dp{0}\", 2, \"{2}\", 80, 443, {0}, \"{1}\" ]".format(_rscount, row["Interface\xff"],row["IPv4"]))
		_rscount +=1
		
	print "[masters]"
	map(print_master, masters)
	print "[minions]"
	map(print_minion, minions)
	print minions_para
	print para4
	print "[lb]"
	lb_count = 0
	for row in lbs:
		if lb_count == 0:
			print("{0} ansible_ssh_host={1} openshift_ip={1} openshift_public_ip={1} openshift_public_hostname={0} openshift_hostname={0} ha_status=MASTER".format( row["Hostname\xff"], row["IPv4"]))
		else:
			print("{0} ansible_ssh_host={1} openshift_ip={1} openshift_public_ip={1} openshift_public_hostname={0} openshift_hostname={0} ha_status=SLAVE".format( row["Hostname\xff"], row["IPv4"]))
		lb_count +=1	
	print "[lb:vars]"
	 
	print "[deployer]"
	print("{0} ansible_ssh_host={1} openshift_ip={1} openshift_hostname={0}".format(deployer["Hostname\xff"], deployer["IPv4"]))

	print "[deployer:vars]"
	
	
	
def discern_vmr(desc, vmr):
	n = desc.find("VMR")
	#print desc
	if n == -1:
		result = False
	elif  desc[n+4] == vmr:
		result = True
	else:
		result = False
	#print result
	return result 


def print_info(row):
	print("{0:5} {1:50} {2:16} {3:32} {4:64}".format(row["POD"],row['Description\xff'], row['IPv4'], row['Hostname\xff'], row['DNS A Records']))

	
def usage_msg(): 

	print "usage: coe_inv.py <inventory spreadsheet in MS-DOS .csv format> <pod> <vmr> --inv (for use with ansible) or --info (easier to read than a spreadsheet)"
	print " Typos in the spreadsheet will mess things up, use VMR 1 as oppposed to 01 We can use variant fromats of spreadsheet/csv as long as the column names and csv format match what the "                   
		
def print_minion(row):
	print("{0} ansible_ssh_host={1}openshift_ip={1} openshift_public_ip={1} openshift_public_hostname={0} openshift_hostname={0} openshift_node_labels=\"{{'network': 'dp1', 'vmrk8s': 'true'}}\" openshift_schedulable=true".format(row['Hostname\xff'], row['IPv4']))

def print_master(row):
	print("{0} ansible_ssh_host={1} openshift_ip={1} openshift_public_ip={1} openshift_public_hostname={0} openshift_hostname={0} openshift_schedulable=false".format(row['Hostname\xff'], row['IPv4']))



if __name__ == '__main__':
	main()