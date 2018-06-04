

clean:
	rm -f *~ *.pyc *.pyo MegaSAS.log MANIFEST


source: clean
	python setup.py sdist


# Due to redhat being ... redhat and bdist being crappy, you may need a one line patch to bdist_rpm
# found in the notes file.
rpm: clean
	python setup.py bdist_rpm


## END OF LINE ##

