from enum import EJECT, Enum, Flag

import numpy as np

# Python Standard Encodings
# https://docs.python.org/3.8/library/codecs.html#standard-encodings

# A STRING constant is a string enclosed by single quotation marks.
# The characters are encoded according to the Windows 1252 character set.
# https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_plc_intro/2529327243.html&id=
TWINCAT_STRING_ENCODING = "cp1252"


class CommandId(np.uint16, Enum):
    """
    Command ID
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115847307.html&id=7738940192708835096
    """

    ADSSRVID_READDEVICEINFO = 0x1
    """Reads the name and the version number of the ADS device."""
    ADSSRVID_READ = 0x2
    """With ADS Read data can be read from an ADS device."""
    ADSSRVID_WRITE = 0x3
    """With ADS Write data can be written to an ADS device."""
    ADSSRVID_READSTATE = 0x4
    """Reads the ADS status and the device status of an ADS device."""
    ADSSRVID_WRITECTRL = 0x5
    """Changes the ADS status and the device status of an ADS device."""
    ADSSRVID_ADDDEVICENOTE = 0x6
    """A notification is created in an ADS device."""
    ADSSRVID_DELDEVICENOTE = 0x7
    """One before defined notification is deleted in an ADS device."""
    ADSSRVID_DEVICENOTE = 0x8
    """Data will carry forward independently from an ADS device to a Client."""
    ADSSRVID_READWRITE = 0x9
    """With ADS ReadWrite data will be written to an ADS device.
    Additionally, data can be read from the ADS device."""


class StateFlag(np.uint16, Enum):
    """
    State Flags
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/115847307.html&id=7738940192708835096
    """

    AMSCMDSF_RESPONSE = 0x1
    AMSCMDSF_ADSCMD = 0x4


class AdsState(np.uint16, Enum):
    """
    Status of the ADS interface of the ADS device
    https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_system/31084171.html&id=
    """

    ADSSTATE_INVALID = 0
    """Invalid state"""
    ADSSTATE_IDLE = 1
    """Idle state"""
    ADSSTATE_RESET = 2
    """Reset state"""
    ADSSTATE_INIT = 3
    """Initialised state"""
    ADSSTATE_START = 4
    """Started"""
    ADSSTATE_RUN = 5
    """Running"""
    ADSSTATE_STOP = 6
    """Stopped"""
    ADSSTATE_SAVECFG = 7
    """Save configuration"""
    ADSSTATE_LOADCFG = 8
    """Load configuration"""
    ADSSTATE_POWERFAILURE = 9
    """Power failure"""
    ADSSTATE_POWERGOOD = 10
    """Power good"""
    ADSSTATE_ERROR = 11
    """Error state"""
    ADSSTATE_SHUTDOWN = 12
    """Shutting down"""
    ADSSTATE_SUSPEND = 13
    """Suspended"""
    ADSSTATE_RESUME = 14
    """Resumed"""
    ADSSTATE_CONFIG = 15
    """System is in config mode"""
    ADSSTATE_RECONFIG = 16
    """System should restart in config mode"""
    ADSSTATE_STOPPING = 17
    """Stopping state"""
    ADSSTATE_INCOMPATIBLE = 18
    """Incompatible state"""
    ADSSTATE_EXCEPTION = 19
    """Exception state"""
    ADSSTATE_MAXSTATES = 20
    """Maximum number of available ads states"""


class DeviceStateMachine(np.uint16, Enum):
    """
    EtherCAT device state machine
    https://infosys.beckhoff.com/english.php?content=../content/1033/tcsystemmanager/1089026187.html&id=
    """

    DEVSTATE_INIT = 0x00
    """Init state"""
    DEVSTATE_PREOP = 0x02
    """Pre-operational state"""
    DEVSTATE_BOOTSTRAP = 0x03
    """Bootstrap state"""
    DEVSTATE_SAFEOP = 0x04
    """Safe-operational state"""
    DEVSTATE_OP = 0x08
    """Operational state"""


class SlaveStateMachine(np.uint8, Enum):
    """
    EtherCAT slave state machine
    https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_ethercat/57122443.html&id=
    """

    SLAVE_STATE_INIT = 0x00
    """Init state"""
    SLAVE_STATE_PREOP = 0x02
    """Pre-operational state"""
    SLAVE_STATE_BOOTSTRAP = 0x03
    """Bootstrap state"""
    SLAVE_STATE_SAFEOP = 0x04
    """Safe-operational state"""
    SLAVE_STATE_OP = 0x08
    """Operational state"""
    SLAVE_STATE_ERROR = 0x10
    """Error state"""
    SLAVE_STATE_INVALID_ID = 0x20
    """Invalid vendorId, productCode, revisionNb or serialNb"""
    SLAVE_STATE_INIT_ERROR = 0x40
    """Initialisation command error"""
    SLAVE_STATE_DISABLED = 0x80
    """Disabled slave"""


class SlaveLinkState(np.uint8, Enum):
    """
    EtherCAT slave link status
    https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_ethercat/57122443.html&id=
    """

    SLAVE_LINK_STATE_OK = 0x00
    """Good ADS link state"""
    SLAVE_LINK_STATE_NOT_PRESENT = 0x01
    """No EtherCAT communication with the EtherCAT slave"""
    SLAVE_LINK_STATE_WITHOUT_COMM = 0x02
    """Error at port X; the port has a link, but no communication is possible via it."""
    SLAVE_LINK_STATE_MISSING_LINK = 0x04
    """Missing communication link at port X"""
    SLAVE_LINK_STATE_ADDITIONAL_LINK = 0x08
    """Additional communication link at port X"""
    SLAVE_LINK_STATE_PORT_A = 0x10
    """Port 0"""
    SLAVE_LINK_STATE_PORT_B = 0x20
    """Port 1"""
    SLAVE_LINK_STATE_PORT_C = 0x40
    """Port 2"""
    SLAVE_LINK_STATE_PORT_D = 0x80
    """Port 3"""


# TwinCAT 2 Reserved Index Groups
# https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclibsystem/11827998603.html&id=
class IndexGroup(np.uint32, Flag, boundary=EJECT):
    """
    Specification of the ADS system services
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/117463563.html&id=
    """

    ADSIGRP_SYM_UPLOAD = 0xF00B
    """Symbol uploads group, used to access the available symbol entries"""
    ADSIGRP_SYM_UPLOADINFO2 = 0xF00F
    """Symbol info uploads group, used to access info about the available symbols"""
    ADSIGRP_COE_LINK = 0xF302
    """IO link data channel, used to access the Can-over-EtherCAT (CoE) parameters"""
    ADSIGR_IODEVICE_STATE_BASE = 0x5000
    """Group used to access information about the IO server"""
    ADSIGRP_MASTER_COUNT_SLAVE = 0x0006
    """Group used to access the number of configured slaves"""
    ADSIGRP_MASTER_SLAVE_ADDRESSES = 0x0007
    """Group used to access the fixed addresses of all slaves configured on a device"""
    ADSIGRP_MASTER_SLAVE_IDENTITY = 0x0011
    """Group used to access the CANopen identity of an EtherCAT slave"""
    ADSIGRP_MASTER_STATEMACHINE = 0x0003
    """Group used to access the state machine of the Master EtherCAT device"""
    ADSIGRP_SLAVE_STATEMACHINE = 0x0009
    """Group used to access the state machine of the slave terminal"""
    ADSIGRP_SLAVE_CRC_COUNTERS = 0x0012
    """Group used to access the CRC counters of all slaves configured on a device"""
    ADSIGRP_MASTER_FRAME_COUNTERS = 0x000C
    """Group used to access the frame counters of an EtherCAT device"""
    TEST_IGRP = 0x0007


class CoEIndex(np.uint32, Enum):
    """
    Specification of the CAN-over-Ethernet (CoE) parameter ranges
    https://infosys.beckhoff.com/english.php?content=../content/1033/ethercatsystem/2469073803.html&id=274367601078044781
    """

    ADS_COE_IDENTIFICATION_PARAMS = 0x1000
    """Range used to access the fixed identity information of a device/terminal"""
    ADS_COE_OPERATIONAL_PARAMS = 0x8000
    """Range used to access the operational and functional parameters"""


class DeviceType(np.uint16, Enum):
    """
    I/O device types
    https://infosys.beckhoff.com/english.php?content=../content/1033/tcplclib_tc2_iofunctions/59217419.html&id=
    """

    IODEVICETYPE_ETHERCAT = 94
    """EtherCAT in direct mode"""


class ErrorCode(np.uint32, Enum):
    """
    ADS Return Codes
    https://infosys.beckhoff.com/english.php?content=../content/1033/tc3_ads_intro/374277003.html&id=4954945278371876402
    """

    ERR_NOERROR = 0x0
    """No error."""
    ERR_INTERNAL = 0x1
    """Internal error."""
    ERR_NORTIME = 0x2
    """No real time."""
    ERR_ALLOCLOCKEDMEM = 0x3
    """Allocation locked - memory error."""
    ERR_INSERTMAILBOX = 0x4
    """Mailbox full - the ADS message could not be sent.
    Reducing the number of ADS messages per cycle will help."""
    ERR_WRONGRECEIVEHMSG = 0x5
    """Wrong HMSG."""
    ERR_TARGETPORTNOTFOUND = 0x6
    """Target port not found - ADS server is not started or is not reachable."""
    ERR_TARGETMACHINENOTFOUND = 0x07
    """Target computer not found - AMS route was not found."""
    ERR_UNKNOWNCMDID = 0x8
    """Unknown command ID."""
    ERR_BADTASKID = 0x9
    """Invalid task ID."""
    ERR_NOIO = 0xA
    """No IO."""
    ERR_UNKNOWNAMSCMD = 0xB
    """Unknown AMS command."""
    ERR_WIN32ERROR = 0xC
    """Win32 error."""
    ERR_PORTNOTCONNECTED = 0xD
    """Port not connected."""
    ERR_INVALIDAMSLENGTH = 0xE
    """Invalid AMS length."""
    ERR_INVALIDAMSNETID = 0xF
    """Invalid AMS Net ID."""
    ERR_LOWINSTLEVEL = 0x10
    """Installation level is too low - TwinCAT 2 license error."""
    ERR_NODEBUGINTAVAILABLE = 0x11
    """No debugging available."""
    ERR_PORTDISABLED = 0x12
    """Port disabled - TwinCAT system service not started."""
    ERR_PORTALREADYCONNECTED = 0x13
    """Port already connected."""
    ERR_AMSSYNC_W32ERROR = 0x14
    """AMS Sync Win32 error."""
    ERR_AMSSYNC_TIMEOUT = 0x15
    """AMS Sync Timeout."""
    ERR_AMSSYNC_AMSERROR = 0x16
    """AMS Sync error."""
    ERR_AMSSYNC_NOINDEXINMAP = 0x17
    """No index map for AMS Sync available."""
    ERR_INVALIDAMSPORT = 0x18
    """Invalid AMS port."""
    ERR_NOMEMORY = 0x19
    """No memory."""
    ERR_TCPSEND = 0x1A
    """TCP send error."""
    ERR_HOSTUNREACHABLE = 0x1B
    """Host unreachable."""
    ERR_INVALIDAMSFRAGMENT = 0x1C
    """Invalid AMS fragment."""
    ERR_TLSSEND = 0x1D
    """TLS send error - secure ADS connection failed."""
    ERR_ACCESSDENIED = 0x1E
    """Access denied - secure ADS access denied."""

    ROUTERERR_NOLOCKEDMEMORY = 0x500
    """Locked memory cannot be allocated."""
    ROUTERERR_RESIZEMEMORY = 0x501
    """The router memory size could not be changed."""
    ROUTERERR_MAILBOXFULL = 0x502
    """The mailbox has reached the maximum number of possible messages."""
    ROUTERERR_DEBUGBOXFULL = 0x503
    """The Debug mailbox has reached the maximum number of possible messages."""
    ROUTERERR_UNKNOWNPORTTYPE = 0x504
    """The port type is unknown."""
    ROUTERERR_NOTINITIALIZED = 0x505
    """The router is not initialized."""
    ROUTERERR_PORTALREADYINUSE = 0x506
    """The port number is already assigned."""
    ROUTERERR_NOTREGISTERED = 0x507
    """The port is not registered."""
    ROUTERERR_NOMOREQUEUES = 0x508
    """The maximum number of ports has been reached."""
    ROUTERERR_INVALIDPORT = 0x509
    """The port is invalid."""
    ROUTERERR_NOTACTIVATED = 0x50A
    """The router is not active."""
    ROUTERERR_FRAGMENTBOXFULL = 0x50B
    """The mailbox has reached the maximum number for fragmented messages."""
    ROUTERERR_FRAGMENTTIMEOUT = 0x50C
    """A fragment timeout has occurred."""
    ROUTERERR_TOBEREMOVED = 0x50D
    """The port is removed."""

    ADSERR_DEVICE_ERROR = 0x0700
    """General device error."""
    ADSERR_DEVICE_SRVNOTSUPP = 0x0701
    """Service is not supported by the server."""
    ADSERR_DEVICE_INVALIDGRP = 0x0702
    """Invalid index group."""
    ADSERR_DEVICE_INVALIDOFFSET = 0x0703
    """Invalid index offset."""
    ADSERR_DEVICE_INVALIDACCESS = 0x0704
    """Reading or writing not permitted."""
    ADSERR_DEVICE_INVALIDSIZE = 0x0705
    """Parameter size not correct."""
    ADSERR_DEVICE_INVALIDDATA = 0x0706
    """Invalid data values."""
    ADSERR_DEVICE_NOTREADY = 0x0707
    """Device is not ready to operate."""
    ADSERR_DEVICE_BUSY = 0x0708
    """Device is busy."""
    ADSERR_DEVICE_INVALIDCONTEXT = 0x0709
    """Invalid operating system context.
    This can result from use of ADS blocks in different tasks.
    (possible resolution includes multitasking synchronization in the PLC)"""
    ADSERR_DEVICE_NOMEMORY = 0x070A
    """Insufficient memory."""
    ADSERR_DEVICE_INVALIDPARM = 0x070B
    """Invalid parameter values."""
    ADSERR_DEVICE_NOTFOUND = 0x070C
    """Not found (files, ...)."""
    ADSERR_DEVICE_SYNTAX = 0x070D
    """Syntax error in file or command."""
    ADSERR_DEVICE_INCOMPATIBLE = 0x070E
    """Objects do not match."""
    ADSERR_DEVICE_EXISTS = 0x070F
    """Object already exists."""
    ADSERR_DEVICE_SYMBOLNOTFOUND = 0x0710
    """Symbol not found."""
    ADSERR_DEVICE_SYMBOLVERSIONINVALID = 0x0711
    """Invalid symbol version.
    This can occur due to an online change. Create a new handle."""
    ADSERR_DEVICE_INVALIDSTATE = 0x0712
    """Device (server) is in invalid state."""
    ADSERR_DEVICE_TRANSMODENOTSUPP = 0x0713
    """AdsTransMode not supported."""
    ADSERR_DEVICE_NOTIFYHNDINVALID = 0x0714
    """Notification handle is invalid."""
    ADSERR_DEVICE_CLIENTUNKNOWN = 0x0715
    """Notification client not registered."""
    ADSERR_DEVICE_NOMOREHDLS = 0x0716
    """No further handle available."""
    ADSERR_DEVICE_INVALIDWATCHSIZE = 0x0717
    """Notification size too large."""
    ADSERR_DEVICE_NOTINIT = 0x0718
    """Device not initialized."""
    ADSERR_DEVICE_TIMEOUT = 0x0719
    """Device has a timeout."""
    ADSERR_DEVICE_NOINTERFACE = 0x071A
    """Interface query failed."""
    ADSERR_DEVICE_INVALIDINTERFACE = 0x071B
    """Wrong interface requested."""
    ADSERR_DEVICE_INVALIDCLSID = 0x071C
    """Class ID is invalid."""
    ADSERR_DEVICE_INVALIDOBJID = 0x071D
    """Object ID is invalid."""
    ADSERR_DEVICE_PENDING = 0x071E
    """Request pending."""
    ADSERR_DEVICE_ABORTED = 0x071F
    """Request is aborted."""
    ADSERR_DEVICE_WARNING = 0x0720
    """Signal warning."""
    ADSERR_DEVICE_INVALIDARRAYIDX = 0x0721
    """Invalid array index."""
    ADSERR_DEVICE_SYMBOLNOTACTIVE = 0x0722
    """Symbol not active."""
    ADSERR_DEVICE_ACCESSDENIED = 0x0723
    """Access denied."""
    ADSERR_DEVICE_LICENSENOTFOUND = 0x0724
    """Missing license."""
    ADSERR_DEVICE_LICENSEEXPIRED = 0x0725
    """License expired."""
    ADSERR_DEVICE_LICENSEEXCEEDED = 0x0726
    """License exceeded."""
    ADSERR_DEVICE_LICENSEINVALID = 0x0727
    """Invalid license."""
    ADSERR_DEVICE_LICENSESYSTEMID = 0x0728
    """License problem: System ID is invalid."""
    ADSERR_DEVICE_LICENSENOTIMELIMIT = 0x0729
    """License not limited in time."""
    ADSERR_DEVICE_LICENSEFUTUREISSUE = 0x072A
    """Licensing problem: time in the future."""
    ADSERR_DEVICE_LICENSETIMETOLONG = 0x072B
    """License period too long."""
    ADSERR_DEVICE_EXCEPTION = 0x072C
    """Exception at system startup."""
    ADSERR_DEVICE_LICENSEDUPLICATED = 0x072D
    """License file read twice."""
    ADSERR_DEVICE_SIGNATUREINVALID = 0x072E
    """Invalid signature."""
    ADSERR_DEVICE_CERTIFICATEINVALID = 0x072F
    """Invalid certificate."""
    ADSERR_DEVICE_LICENSEOEMNOTFOUND = 0x0730
    """Public key not known from OEM."""
    ADSERR_DEVICE_LICENSERESTRICTED = 0x0731
    """License not valid for this system ID."""
    ADSERR_DEVICE_LICENSEDEMODENIED = 0x0732
    """Demo license prohibited."""
    ADSERR_DEVICE_INVALIDFNCID = 0x0733
    """Invalid function ID."""
    ADSERR_DEVICE_OUTOFRANGE = 0x0734
    """Outside the valid range."""
    ADSERR_DEVICE_INVALIDALIGNMENT = 0x0735
    """Invalid alignment."""
    ADSERR_DEVICE_LICENSEPLATFORM = 0x0736
    """Invalid platform level."""
    ADSERR_DEVICE_FORWARD_PL = 0x0737
    """Context - forward to passive level."""
    ADSERR_DEVICE_FORWARD_DL = 0x0738
    """Context - forward to dispatch level."""
    ADSERR_DEVICE_FORWARD_RT = 0x0739
    """Context - forward to real time."""
    ADSERR_CLIENT_ERROR = 0x0740
    """Client error."""
    ADSERR_CLIENT_INVALIDPARM = 0x0741
    """Service contains an invalid parameter."""
    ADSERR_CLIENT_LISTEMPTY = 0x0742
    """Polling list is empty."""
    ADSERR_CLIENT_VARUSED = 0x0743
    """Var connection already in use."""
    ADSERR_CLIENT_DUPLINVOKEID = 0x0744
    """The called ID is already in use."""
    ADSERR_CLIENT_SYNCTIMEOUT = 0x0745
    """Timeout has occurred - no response from the remote terminal in the ADS timeout.
    The route setting of the remote terminal may be configured incorrectly."""
    ADSERR_CLIENT_W32ERROR = 0x0746
    """Error in Win32 subsystem."""
    ADSERR_CLIENT_TIMEOUTINVALID = 0x0747
    """Invalid client timeout value."""
    ADSERR_CLIENT_PORTNOTOPEN = 0x0748
    """Port not open."""
    ADSERR_CLIENT_NOAMSADDR = 0x0749
    """No AMS address."""
    ADSERR_CLIENT_SYNCINTERNAL = 0x0750
    """Internal error in Ads sync."""
    ADSERR_CLIENT_ADDHASH = 0x0751
    """Hash table overflow."""
    ADSERR_CLIENT_REMOVEHASH = 0x0752
    """Key not found in the table."""
    ADSERR_CLIENT_NOMORESYM = 0x0753
    """No symbols in the cache."""
    ADSERR_CLIENT_SYNCRESINVALID = 0x0754
    """Invalid response received."""
    ADSERR_CLIENT_SYNCPORTLOCKED = 0x0755
    """Sync Port is locked."""
    ADSERR_CLIENT_REQUESTCANCELLED = 0x0756
    """The request was cancelled."""

    RTERR_INTERNAL = 0x1000
    """Internal error in the real-time system."""
    RTERR_BADTIMERPERIODS = 0x1001
    """Timer value is not valid."""
    RTERR_INVALIDTASKPTR = 0x1002
    """Task pointer has the invalid value 0 (zero)."""
    RTERR_INVALIDSTACKPTR = 0x1003
    """Stack pointer has the invalid value 0 (zero)."""
    RTERR_PRIOEXISTS = 0x1004
    """The request task priority is already assigned."""
    RTERR_NOMORETCB = 0x1005
    """No free TCB (Task Control Block) available. The maximum number of TCBs is 64."""
    RTERR_NOMORESEMAS = 0x1006
    """No free semaphores available. The maximum number of semaphores is 64."""
    RTERR_NOMOREQUEUES = 0x1007
    """No free space available in the queue.
    The maximum number of positions in the queue is 64."""
    RTERR_EXTIRQALREADYDEF = 0x100D
    """An external synchronization interrupt is already applied."""
    RTERR_EXTIRQNOTDEF = 0x100E
    """No external sync interrupt applied."""
    RTERR_EXTIRQINSTALLFAILED = 0x100F
    """Application of the external synchronization interrupt has failed."""
    RTERR_IRQLNOTLESSOREQUAL = 0x1010
    """Call of a service function in the wrong context"""
    RTERR_VMXNOTSUPPORTED = 0x1017
    """Intel VT-x extension is not supported."""
    RTERR_VMXDISABLED = 0x1018
    """Intel VT-x extension is not enabled in the BIOS."""
    RTERR_VMXCONTROLSMISSING = 0x1019
    """Missing function in Intel VT-x extension."""
    RTERR_VMXENABLEFAILS = 0x101A
    """Activation of Intel VT-x fails."""
