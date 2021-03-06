from captcha.key_press_vbox import *
import logging
import random
import numpy as np
import pymouse
from vbox_manager import VirtualBoxController
from configobj import ConfigObj


class MouseMover(VirtualBoxController):
    def __init__(self, vbox_mode):
        if vbox_mode:
            super().__init__()
        self.mouse=pymouse.PyMouse()
        self.vbox_mode=vbox_mode

    def click(self, x, y):
        if self.vbox_mode:
            self.mouse_move_vbox(x, y)
            self.mouse_click_vbox(x, y)
        else:
            self.mouse.move(x, y)
            self.mouse.click(x, y)

        time.sleep(np.random.uniform(0.2, 0.3, 1)[0])

    def mouse_mover(self, x1, y1, x2, y2):
        speed = .4
        stepMin = 7
        stepMax = 50
        rd1 = int(np.round(np.random.uniform(stepMin, stepMax, 1)[0]))
        rd2 = int(np.round(np.random.uniform(stepMin, stepMax, 1)[0]))

        xa = list(range(x1, x2, rd1))
        ya = list(range(y1, y2, rd2))

        for k in range(0, max(0, len(xa) - len(ya))):
            ya.append(y2)
        for k in range(0, max(0, len(ya) - len(xa))):
            xa.append(x2)

        xTremble = 20
        yTremble = 20

        for i in range(len(max(xa, ya))):
            x = xa[i] + int(+random.random() * xTremble)
            y = ya[i] + int(+random.random() * yTremble)
            if self.vbox_mode:
                self.mouse_move_vbox(x, y)
            else:
                self.mouse.move(x, y)
            time.sleep(np.random.uniform(0.01 * speed, 0.03 * speed, 1)[0])

        if self.vbox_mode:
            self.mouse_move_vbox(x2, y2)
        else:
            self.mouse.move(x2, y2)



    def mouse_clicker(self, x2, y2, buttonToleranceX, buttonToleranceY):
        xrand = int(np.random.uniform(0, buttonToleranceX, 1)[0])
        yrand = int(np.random.uniform(0, buttonToleranceY, 1)[0])

        if self.vbox_mode:
            self.mouse_move_vbox(x2 + xrand, y2 + yrand)
        else:
            self.mouse.move(x2 + xrand, y2 + yrand)

        time.sleep(np.random.uniform(0.1, 0.2, 1)[0])

        self.click(x2 + xrand, y2 + yrand)

        time.sleep(np.random.uniform(0.1, 0.5, 1)[0])

class MouseMoverTableBased(MouseMover):
    def __init__(self, pokersite,betplus_inc=1,bet_bluff_inc=1):
        config = ConfigObj("config.ini")

        try:
            mouse_control = config['control']
            if mouse_control!='Direct mouse control': self.vbox_mode=True
            else: self.vbox_mode = False
        except:
            self.vbox_mode = False

        super().__init__(self.vbox_mode)

        # amount,pre-delay,x1,xy,x1tolerance,x2tolerance
        with open('coordinates.txt','r') as inf:
            c = eval(inf.read())
            coo=c['mouse_mover']

        self.coo=coo[pokersite[0:2]]


    def enter_captcha(self, captchaString, topleftcorner):
        logger.warning("Entering Captcha: " + str(captchaString))
        buttonToleranceX = 30
        buttonToleranceY = 0
        tlx = topleftcorner[0]
        tly = topleftcorner[1]
        (x1, y1) = self.mouse.position()
        x2 = 30 + tlx
        y2 = 565 + tly
        self.mouse_mover(x1, y1, x2, y2)
        self.mouse_clicker(x2, y2, buttonToleranceX, buttonToleranceY)
        try:
            write_characters_to_virtualbox(captchaString, "win")
        except:
            logger.info("Captcha Error")


    def mouse_action(self, decision, topleftcorner, logger):
        if decision == 'Check Deception': decision = 'Check'
        if decision == 'Call Deception': decision = 'Call'

        logger.info("Moving Mouse: "+str(decision))
        tlx = int(topleftcorner[0])
        tly = int(topleftcorner[1])

        logger.info("Mouse moving to: "+decision)
        for action in self.coo[decision]:
            for i in range (int(action[0])):
                time.sleep(np.random.uniform(0, action[1], 1)[0])
                logger.debug("Mouse action:"+str(action))
                (x1, y1) = self.mouse.position()
                self.mouse_mover(x1, y1, action[2]+ tlx, action[3]+ tly)
                self.mouse_clicker(action[2]+ tlx, action[3]+ tly,action[4], action[5])

        xscatter = int(np.round(np.random.uniform(1700, 2000, 1), 0))
        yscatter = int(np.round(np.random.uniform(10, 400, 1), 0))

        time.sleep(np.random.uniform(0.4, 1.0, 1)[0])
        (x2, y2) = self.mouse.position()
        logger.debug("Moving mouse away: "+str(x2)+","+str(y2)+","+str(xscatter)+","+str(yscatter))
        self.mouse_mover(x2, y2, xscatter, yscatter)

if __name__=="__main__":
    logger = logging.getLogger()
    m=MouseMoverTableBased('PP',5,5)
    topleftcorner=[22,22]
    m.mouse_action("BetPlus", topleftcorner, logger)