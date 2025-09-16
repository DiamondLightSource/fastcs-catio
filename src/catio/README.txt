/*
Note that some changes in the venv repositories had to be made 
to get some additional functionalities
*/

############ Additions in FastCS/src/fastcs

# fastcs/src/fastcs/backend.py
    async def __del__(self):
        self._stop_scan_tasks()
        await self._controller.close()

    def _scan_done(self, task: asyncio.Task):
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            raise FastCSError(
                "Exception raised in scan method of "
                f"{self._controller.__class__.__name__}"
            ) from e


# controller.py
    async def close(self) -> None:
        pass


# launch.py
    def end(self):
        close = asyncio.ensure_future(self.close())
        self._loop.run_until_complete(close)
    
    async def close(self) -> None:
        coros = [self._backend.__del__()]
        await asyncio.gather(*coros)



############ Additions in PythonSoftIOC/src/softIoc/imports.py

callbackSetQueueSize = dbCore.callbackSetQueueSize
callbackSetQueueSize.argtypes = (c_int,)
callbackSetQueueSize.errcheck = expect_success

__all__ = [
    'get_field_offsets',
    'create_callback_capsule',
    'signal_processing_complete',
    'registryDeviceSupportAdd',
    'IOSCANPVT', 'scanIoRequest', 'scanIoInit',
    'dbLoadDatabase',
    'callbackSetQueueSize',
    'recGblResetAlarms',
]
