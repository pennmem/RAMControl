from extendedPyepl import *
import time
from RAMControl import RAMControl, RAMCallbacks
from FR import FRExperimentRunner

class testRunner(FRExperimentRunner):

    def __init__(self, fr_experiment, clock, log, mathlog, video, audio, callbacks, config):
        self.fr_experiment = fr_experiment
        self.clock = clock
        self.log = log
        self.mathlog = mathlog
        self.video = video
        self.audio = audio
        self.callbacks = callbacks
        self._on_screen = True
        self.config = config

    def _simultaneous_states(self):
        self.clock.tare()
        self.log_message('SIMULTANEOUS_ON')
        self._send_state_message('SIMULTANEOUS_1', True)
        self._send_state_message('SIMULTANEOUS_2', True)
        self.clock.delay(750)
        self.clock.wait()
        self.log_message('SIMULTANEOUS_OFF')
        self._send_state_message('SIMULTANEOUS_1', False)
        self._send_state_message('SIMULTANEOUS_2', False)

    def _on_word_update(self, *args):
        self._send_state_message('WORD', self._on_screen)
        self._on_screen = not self._on_screen

    def _state_with_present(self):
        word_text = CustomText('WORD')
        callback = self._on_word_update
        self._on_screen = True
        self._offscreen_callback = None
        t_on, t_off = word_text.presentWithCallback(clk=self.clock,
                                                    duration=750,
                                                    updateCallback=callback)
        self.log_message('WORD_ON', t_on)
        self.log_message('WORD_OFF', t_off)

    def _simple_state(self):
        self.clock.tare()
        self._send_state_message('SIMPLE', True)
        self.log_message('SIMPLE_ON')
        self.clock.delay(750)
        self.clock.wait()
        self.clock.tare()
        self._send_state_message('SIMPLE', False)
        self.log_message('SIMPLE_OFF')

    def _on_orient_update(self, *args):
        if self._on_screen:
            self._send_state_message('ORIENT', True)
        else:
            self._send_state_message('ORIENT', False)
        self._on_screen = not self._on_screen

    def _state_with_flash_stimulus(self):
        self._on_screen = True
        self._state_name = 'ORIENT'
        on_update = self._on_orient_update
        self.video.addUpdateCallback(on_update)
        cbref = self.video.update_callbacks[-1]
        t_on, t_off = flashStimulusWithOffscreenTimestamp(Text('++'),
                                                          clk=self.clock,
                                                          duration=750)
        self.log_message('ORIENT_ON', t_on)
        self.log_message('ORIENT_OFF', t_off)
        self.video.removeUpdateCallback(cbref)

    def run(self, num_repeats=100):
        fns = [self._simultaneous_states]*num_repeats
               #self._state_with_present,
               #self._simple_state,
               #self._state_with_flash_stimulus] * num_repeats
        random.shuffle(fns)
        for i, fn in enumerate(fns):
            if i % 10 == 0:
                self._send_sync_np()
                self._resynchronize(True)
                self.clock.delay(500)
                self.clock.wait()
            fn()
            self.clock.delay(500)
            self.clock.wait()


def connect_to_control_pc(exp, video, config, callbacks):
    """
    Establish connection to control PC
    """
    if not config['control_pc']:
        return
    clock = PresentationClock()
    control = RAMControl.get_instance()
    video.clear('black')
    if control.ready_control_pc(clock,
                                callbacks,
                                config,
                                exp.getOptions().get('subject'),
                                0):
        waitForAnyKey(clock,
                      Text('Cannot sync to control PC'))
        exit(1)



if __name__ == '__main__':
    exp = Experiment(use_eeg=False)
    exp.parseArgs()
    exp.setup()

    exp.setBreak()

    config = exp.getConfig()

    exp.setSession(0)
    log = LogTrack('session')

    video = VideoTrack('video')
    clock = PresentationClock()

    callbacks = RAMCallbacks(config, clock, video)

    connect_to_control_pc(exp, video, config.sys2, callbacks)

    runner = testRunner(None,
                        clock,
                        log,
                        None,
                        video,
                        None,
                        callbacks, 
                        config)

    runner.run()
