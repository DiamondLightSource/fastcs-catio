This prompt was used to generate the initial versions of the architecture markdown.

Add comprehensive architecture documentation for the catio python project to docs/explanations. The intention of catio is that it has two halves separated by a clean API as follows:
1. A fastCS implementation of an EPICS IOC which exposes a set of Process Variables for controlling devices on an Ethercat Bus
2. An ADS client that provides an API for the above to call (implemented in client.py) and communicates with a TwinCAT ADS server running on a Beckhoff PLC.

See ADS reference here: https://infosys.beckhoff.com/english.php?content=../content/1033/tcinfosys3/11291871243.html&id=6446904803799887467

I'd like 4 separate markdown files:
1. An overview of the architecture of the catio project, including a diagram showing the two halves and how they interact.
2. A detailed explanation of the fastCS EPICS IOC implementation.
3. A detailed explanation of the ADS client implementation.
4. A discussion of any flaws in the decoupling of the two halves via the API, and any potential improvements that could be made.
