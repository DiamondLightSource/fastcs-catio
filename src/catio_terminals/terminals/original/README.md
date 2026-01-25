# original terminal definitions

These files were originally created by introspecting the results of running Greg's original tool against the read hardware.

Then the types used in fastCS were mapped to the symbols defined in the XML files.


The types that this resulted in include compound types such as `AI Standard Channel 1_TYPE`.

I understand that these are related to types used in the code to represent things at the fastCS level.

TODO: we need to work out how to make this work in the new YAML based architecture.

# new terminal definitions files

The files in the folder above are made from looking in the XML definitions for all the symbols defined for each terminal type and selecting all of them. As performed by this script: `scripts/cleanup_yaml.py`

So they represent the low level set of symbols defined by ADS itself.
