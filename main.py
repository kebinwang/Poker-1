import threading
from gui.gui_qt_logic import *
import matplotlib
matplotlib.use('Qt5Agg')
import operator
import os.path
import cv2  # opencv 3.0
import pytesseract
import re
from PIL import Image, ImageGrab, ImageDraw, ImageFilter
from decisionmaker.decisionmaker2 import *
from decisionmaker.montecarlo_v3 import *
from mouse_mover import *
import inspect
from captcha.captcha_manager import solve_captcha
from vbox_manager import VirtualBoxController
from functools import lru_cache

version=1.5

class History(object):
    def __init__(self):
        # keeps values of the last round
        self.previousPot = 0
        self.previousCards = []
        self.myLastBet = 0
        self.histGameStage = ""
        self.myFundsHistory = [2.0]
        self.losses = 0
        self.wins = 0
        self.totalGames = 0
        self.GameID = int(np.round(np.random.uniform(0, 999999999), 0))  # first game ID
        self.lastRoundGameID = 0
        self.lastSecondRoundAdjustment = 0
        self.lastGameID = "0"
        self.histDecision = 0
        self.histEquity = 0
        self.histMinCall = 0
        self.histMinBet = 0
        self.histPlayerPots = 0

class Table(object):
    # General tools that are used to operate the pokerbot and are valid for all tables
    def __init__(self):
        self.load_templates()
        self.load_coordinates()

    def load_templates(self):
        self.cardImages = dict()
        self.img = dict()
        self.tbl=p.selected_strategy['pokerSite']
        values = "23456789TJQKA"
        suites = "CDHS"
        for x in values:
            for y in suites:
                name = "pics/" + self.tbl[0:2] + "/" + x + y + ".png"
                if os.path.exists(name) == True:
                    self.img[x + y] = Image.open(name)
                    self.cardImages[x + y] = cv2.cvtColor(np.array(self.img[x + y]), cv2.COLOR_BGR2RGB)
                    # (thresh, self.cardImages[x + y]) =
                    # cv2.threshold(self.cardImages[x + y], 128, 255,
                    # cv2.THRESH_BINARY | cv2.THRESH_OTSU)
                else:
                    logger.critical("Card Temlate File not found: " + str(x) + str(y) + ".png")

        name = "pics/" + self.tbl[0:2] + "/button.png"
        template = Image.open(name)
        self.button = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/topleft.png"
        template = Image.open(name)
        self.topLeftCorner = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/coveredcard.png"
        template = Image.open(name)
        self.coveredCardHolder = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/imback.png"
        template = Image.open(name)
        self.ImBack = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/check.png"
        template = Image.open(name)
        self.check = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/call.png"
        template = Image.open(name)
        self.call = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/smalldollarsign1.png"
        template = Image.open(name)
        self.smallDollarSign1 = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        if self.tbl[0:2] == "PP":
            name = "pics/" + self.tbl[0:2] + "/smalldollarsign2.png"
            template = Image.open(name)
            self.smallDollarSign2 = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/allincallbutton.png"
        template = Image.open(name)
        self.allInCallButton = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/lostEverything.png"
        template = Image.open(name)
        self.lostEverything = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

        name = "pics/" + self.tbl[0:2] + "/dealer.png"
        template = Image.open(name)
        self.dealer = cv2.cvtColor(np.array(template), cv2.COLOR_BGR2RGB)

    def load_coordinates(self):
        with open('coordinates.txt','r') as inf:
            c = eval(inf.read())
            self.coo=c['screen_scraping']

    def take_screenshot(self,initial):
        if not terminalmode and initial:
            ui_action_and_signals.signal_status.emit("")
            ui_action_and_signals.signal_progressbar_reset.emit()
            if p.exit_thread == True: sys.exit()

            if p.pause == True:
                while p.pause == True:
                    time.sleep(1)
                    if p.exit_thread == True: sys.exit()




        time.sleep(0.1)
        config = ConfigObj("config.ini")
        control = config['control']
        if control=='Direct mouse control':
            self.entireScreenPIL = ImageGrab.grab()

        else:
            try:
                vb = VirtualBoxController()
                self.entireScreenPIL = vb.get_screenshot_vbox()
                logger.info("Screenshot taken from virtual machine")
            except:
                logger.warning("No virtual machine found")
                self.entireScreenPIL = ImageGrab.grab()


        if not terminalmode:ui_action_and_signals.signal_status.emit(str(p.current_strategy))
        if not terminalmode: ui_action_and_signals.signal_progressbar_increase.emit(5)
        return True

    def find_template_on_screen(self, template, screenshot, threshold):
        # 'cv2.TM_CCOEFF', 'cv2.TM_CCOEFF_NORMED', 'cv2.TM_CCORR',
        # 'cv2.TM_CCORR_NORMED', 'cv2.TM_SQDIFF', 'cv2.TM_SQDIFF_NORMED']
        method = eval('cv2.TM_SQDIFF_NORMED')
        # Apply template Matching
        res = cv2.matchTemplate(screenshot, template, method)
        loc = np.where(res <= threshold)

        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        # If the method is TM_SQDIFF or TM_SQDIFF_NORMED, take minimum
        if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            bestFit = min_loc
        else:
            bestFit = max_loc

        count = 0
        points = []
        for pt in zip(*loc[::-1]):
            # cv2.rectangle(img, pt, (pt[0] + w, pt[1] + h), (0,0,255), 2)
            count += 1
            points.append(pt)
        # plt.subplot(121),plt.imshow(res)
        # plt.subplot(122),plt.imshow(img,cmap = 'jet')
        # plt.imshow(img, cmap = 'gray', interpolation = 'bicubic')
        # plt.show()
        return count, points, bestFit

    def get_ocr_float(self, img_orig, name):
        def fix_number(t):
            t = t.replace("I", "1").replace("O", "0").replace("o", "0")\
                .replace("-", ".").replace("D", "0").replace("I","1").replace("_",".").replace("-", ".")
            t = re.sub("[^0123456789\.]", "", t)
            try:
                if t[0] == ".": t = t[1:]
            except: pass
            try:
                if t[-1] == ".": t = t[0:-1]
            except: pass
            try:
                if t[-1]==".": t = t[0:-1]
            except: pass
            try:
                if t[-1] == "-": t = t[0:-1]
            except: pass
            return t

        try:
            img_orig.save('pics/ocr_debug_' + name + '.png')
        except:
            logger.warning("Coulnd't safe debugging png file for ocr")

        basewidth = 200
        wpercent = (basewidth / float(img_orig.size[0]))
        hsize = int((float(img_orig.size[1]) * float(wpercent)))
        img_resized = img_orig.resize((basewidth, hsize), Image.ANTIALIAS)

        img_min = img_resized.filter(ImageFilter.MinFilter)
        #img_med = img_resized.filter(ImageFilter.MedianFilter)
        img_mod = img_resized.filter(ImageFilter.ModeFilter).filter(ImageFilter.SHARPEN)

        lst = []
        # try:
        #    lst.append(pytesseract.image_to_string(img_orig, none, false,"-psm 6"))
        # except exception as e:
        #    logger.error(str(e))
        try:
            lst.append(pytesseract.image_to_string(img_min, None, False, "-psm 6"))
        except Exception as e:
            logger.warning(str(e))
            try:
                self.entireScreenPIL.save('pics/err_debug_fullscreen.png')
            except:
                logger.warning("Coulnd't safe debugging png file for ocr")
        # try:
        #    lst.append(pytesseract.image_to_string(img_med, None, False, "-psm 6"))
        # except Exception as e:
        #    logger.error(str(e))


        try:
            if fix_number(lst[0])=='':
                lst.append(pytesseract.image_to_string(img_mod, None, False, "-psm 6"))
        except Exception as e:
            logger.warning(str(e))
            try:
                self.entireScreenPIL.save('pics/err_debug_fullscreen.png')
            except:
                logger.warning("Coulnd't safe debugging png file for ocr")

        try:
            final_value = ''
            for i, j in enumerate(lst):
                logger.debug("OCR of " + name + " method " + str(i) + ": " + str(j))
                lst[i] = fix_number(lst[i]) if lst[i] != '' else lst[i]
                final_value = lst[i] if final_value == '' else final_value

            logger.info(name + " FINAL VALUE: " + str(final_value))
            return float(final_value)

        except Exception as e:
            logger.warning("Pytesseract Error in recognising " + name)
            logger.warning(str(e))
            try:
                self.entireScreenPIL.save('pics/err_debug_fullscreen.png')
            except:
                pass
            return ''

    def call_genetic_algorithm(self):
        if not terminalmode:
            ui_action_and_signals.signal_progressbar_increase.emit(5)
            ui_action_and_signals.signal_status.emit("Updating charts")
        n = L.get_game_count(p.current_strategy)
        lg = int(
            p.selected_strategy['considerLastGames'])  # only consider lg last games to see if there was a loss
        f = L.get_strategy_return(p.current_strategy, lg)
        if not terminalmode:  ui_action_and_signals.signal_lcd_number_update.emit('gamenumber',int(n))
        if not terminalmode:  ui_action_and_signals.signal_lcd_number_update.emit('winnings', f)
        logger.info("Game #" + str(n) + " - Last " + str(lg) + ": $" + str(f))
        if n % int(p.selected_strategy['strategyIterationGames']) == 0 and f < float(
                p.selected_strategy['minimumLossForIteration']):
            if not terminalmode: ui_action_and_signals.signal_status.emit("***Improving current strategy***")
            logger.info("***Improving current strategy***")
            #winsound.Beep(500, 100)
            GeneticAlgorithm(True, logger, L)
            p.read_strategy()
        else:
            logger.debug("Criteria not met for running genetic algorithm. Recommendation would be as follows:")
            if n % 50 == 0: GeneticAlgorithm(False, logger, L)

    def crop_image(self, original, left, top, right, bottom):
        # original.show()
        width, height = original.size  # Get dimensions
        cropped_example = original.crop((left, top, right, bottom))
        # cropped_example.show()
        return cropped_example

    def find_item_location_in_crop(self,x1,y1,x2,y2,template,screentho):
        pass

class TableScreenBased(Table):
    def get_top_left_corner(self):
        self.current_strategy=p.current_strategy
        img = cv2.cvtColor(np.array(self.entireScreenPIL), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.topLeftCorner, img, 0.01)
        if count == 1:
            self.tlc = points[0]
            logger.debug("Top left corner found")
            t.timeout_start = time.time()
            return True
        else:

            if terminalmode == False:
                ui_action_and_signals.signal_status.emit(self.tbl + " not found yet")
                ui_action_and_signals.signal_progressbar_reset.emit()
            logger.debug("Top left corner NOT found")
            time.sleep(1)
            return False

    def check_for_button(self):
        func_dict=self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        cards = ' '.join(t.mycards)
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1]+func_dict['y1'],self.tlc[0]+func_dict['x2'], self.tlc[1] + func_dict['y2'])
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.button, img, func_dict['tolerance'])

        if count > 0:
            if not terminalmode: ui_action_and_signals.signal_status.emit("Buttons found, cards: " + str(cards))
            logger.info("Buttons Found, cards: " + str(cards))
            return True

        else:
            logger.debug("No buttons found")
            return False

    def check_for_checkbutton(self):
        func_dict=self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode: ui_action_and_signals.signal_status.emit("Check for Check")
        if not terminalmode: ui_action_and_signals.signal_progressbar_increase.emit(5)
        logger.debug("Checking for check button")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.check, img, func_dict['tolerance'])

        if count > 0:
            self.checkButton = True
            self.currentCallValue = 0.0
            logger.debug("check button found")
        else:
            self.checkButton = False
            logger.debug("no check button found")
        logger.debug("Check: " + str(self.checkButton))
        return True

    def check_for_captcha(self, mouse):
        # func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        # if func_dict['active']:
        #     ChatWindow = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
        #                             self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        #     basewidth = 500
        #     wpercent = (basewidth / float(ChatWindow.size[0]))
        #     hsize = int((float(ChatWindow.size[1]) * float(wpercent)))
        #     ChatWindow = ChatWindow.resize((basewidth, hsize), Image.ANTIALIAS)
        #     # ChatWindow.show()
        #     try:
        #         t.chatText = (pytesseract.image_to_string(ChatWindow, None,
        #         False, "-psm 6"))
        #         t.chatText = re.sub("[^abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\.]",
        #         "", t.chatText)
        #         keyword1 = 'disp'
        #         keyword2 = 'left'
        #         keyword3 = 'pic'
        #         keyword4 = 'key'
        #         keyword5 = 'lete'
        #         logger.debug("Recognised text: "+t.chatText)
        #
        #         if ((t.chatText.find(keyword1) > 0) or (t.chatText.find(keyword2)
        #         > 0) or (
        #                     t.chatText.find(keyword3) > 0) or
        #                     (t.chatText.find(keyword4) > 0) or (
        #                     t.chatText.find(keyword5) > 0)):
        #             logger.warning("Submitting Captcha")
        #             captchaIMG = self.crop_image(self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1_2'], self.tlc[1] + func_dict['y1_2'],
        #                             self.tlc[0] + func_dict['x2_2'], self.tlc[1] + func_dict['y2_2']))
        #             captchaIMG.save("pics/captcha.png")
        #             # captchaIMG.show()
        #             time.sleep(0.5)
        #             t.captcha = solve_captcha("pics/captcha.png")
        #             mouse.enter_captcha(t.captcha)
        #             logger.info("Entered captcha: "+str(t.captcha))
        #     except:
        #         logger.warning("CheckingForCaptcha Error")
        return True

    def check_for_imback(self, mouse):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        # Convert RGB to BGR
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.ImBack, img, func_dict['tolerance'])
        if count > 0:
            if not terminalmode: ui_action_and_signals.signal_status.emit("I am back found")
            mouse.mouse_action("Imback", self.tlc, logger)
            return False
        else:
            return True

    def check_for_call(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        logger.debug("Check for Call")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.call, img, func_dict['tolerance'])
        if count > 0:
            self.callButton = True
            logger.debug("Call button found")
        else:
            self.callButton = False
            logger.info("Call button NOT found")
            pil_image.save("pics/debug_nocall.png")
        return True

    def check_for_allincall(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        logger.debug("Check for All in call button")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        # Convert RGB to BGR
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.allInCallButton, img, 0.01)
        if count > 0:
            self.allInCallButton = True
            logger.debug("All in call button found")
        else:
            self.allInCallButton = False
            logger.debug("All in call button not found")
        return True

    def get_table_cards(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        logger.debug("Get Table cards")
        self.cardsOnTable = []
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])

        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)


        for key, value in self.cardImages.items():
            template = value
            method = eval('cv2.TM_SQDIFF_NORMED')
            res = cv2.matchTemplate(img, template, method)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            if min_val < 0.01:
                self.cardsOnTable.append(key)

        self.gameStage = ''

        if len(self.cardsOnTable) < 1:
            self.gameStage = "PreFlop"
        elif len(self.cardsOnTable) == 3:
            self.gameStage = "Flop"
        elif len(self.cardsOnTable) == 4:
            self.gameStage = "Turn"
        elif len(self.cardsOnTable) == 5:
            self.gameStage = "River"

        if self.gameStage == '':
            logger.critical("Table cards not recognised correctly")
            exit()

        logger.info("Gamestage: " + self.gameStage)
        logger.info("Cards on table: " + str(self.cardsOnTable))

        return True

    def get_my_cards(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        def go_through_each_card(img, debugging):
            dic = {}
            for key, value in self.cardImages.items():
                template = value
                method = eval('cv2.TM_SQDIFF_NORMED')

                # Apply template Matching
                # kernel = np.ones((5, 5), np.float32) / 25
                # img = cv2.filter2D(img, -1, kernel)
                # template = cv2.filter2D(template, -1, kernel)

                res = cv2.matchTemplate(img, template, method)

                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                # If the method is TM_SQDIFF or TM_SQDIFF_NORMED, take minimum
                if method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                    top_left = min_loc
                else:
                    top_left = max_loc
                if min_val < 0.01:
                    self.mycards.append(key)
                if debugging:
                    dic[key] = min_val

            if debugging:
                dic = sorted(dic.items(), key=operator.itemgetter(1))
                logger.error("Analysing cards: " + str(dic))

        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        self.mycards = []
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])

        # pil_image.show()
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        # (thresh, img) = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY |
        # cv2.THRESH_OTSU)
        go_through_each_card(img, False)

        if len(self.mycards) == 2:
            self.myFundsChange = float(self.myFunds) - float(str(h.myFundsHistory[-1]).strip('[]'))
            logger.info("My cards: " + str(self.mycards))
            return True
        else:
            logger.debug("Did not find two player cards: " + str(self.mycards))
            # go_through_each_card(img,True)
            return False

    def get_covered_card_holders(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        if terminalmode == False: ui_action_and_signals.signal_status.emit("Analyse other players and position")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        # Convert RGB to BGR
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.coveredCardHolder, img, func_dict['tolerance'])
        self.PlayerNames = []
        self.PlayerFunds = []

        count = 0
        for pt in points:
            if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(1)
            # cv2.rectangle(img, pt, (pt[0] + w, pt[1] + h), (0,0,255), 2)
            count += 1
            playerNameImage = pil_image.crop((pt[0] - (955 - 890), pt[1] + 270 - 222, pt[0] + 20, pt[1] + +280 - 222))
            basewidth = 500
            wpercent = (basewidth / float(playerNameImage.size[0]))
            hsize = int((float(playerNameImage.size[1]) * float(wpercent)))
            playerNameImage = playerNameImage.resize((basewidth, hsize), Image.ANTIALIAS)
            # playerNameImage.show()
            try:
                recognizedText = (pytesseract.image_to_string(playerNameImage, None, False, "-psm 6"))
                recognizedText = re.sub("[^abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789]", "",
                                        recognizedText)
                self.PlayerNames.append(recognizedText)
            except:
                logger.debug("Pyteseract error in player name recognition")

            playerFundsImage = pil_image.crop(
                (pt[0] - (955 - 890) + 10, pt[1] + 270 - 222 + 20, pt[0] + 10, pt[1] + +280 - 222 + 22))
            basewidth = 500
            wpercent = (basewidth / float(playerNameImage.size[0]))
            hsize = int((float(playerNameImage.size[1]) * float(wpercent)))
            playerFundsImage = playerFundsImage.resize((basewidth, hsize), Image.ANTIALIAS)
            # playerFundsImage = playerFundsImage.filter(ImageFilter.MaxFilter)
            # playerFundsImage.show()


            self.PlayerFunds.append(self.get_ocr_float(playerFundsImage,'PlayerFunds'))


        logger.debug("Player Names: " + str(self.PlayerNames))
        logger.debug("Player Funds: " + str(self.PlayerFunds))
        if not terminalmode: ui_action_and_signals.signal_status.emit("Analysing other players")

        # plt.subplot(122),plt.imshow(img,cmap = 'jet')
        # plt.imshow(img, cmap = 'gray', interpolation = 'bicubic')
        # plt.show()
        self.coveredCardHolders = np.round(count)

        logger.info("Covered cardholders: " + str(self.coveredCardHolders))

        if self.coveredCardHolders == 1:
            self.isHeadsUp = True
            logger.debug("HeadSUP detected!")
        else:
            self.isHeadsUp = False

        if self.coveredCardHolders > 0:
            return True
        else:
            logger.info("No other players found. Assuming 1 player")
            self.coveredCardHolders = 1
            return True

    def get_played_players(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        if terminalmode == False: ui_action_and_signals.signal_status.emit("Analyse past players")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])

        im = pil_image
        x, y = im.size
        eX, eY = 280, 150  # Size of Bounding Box for ellipse

        bbox = (x / 2 - eX / 2, y / 2 - eY / 2, x / 2 + eX / 2, y / 2 + eY / 2 - 20)
        rectangle1 = (func_dict['x1_1'],func_dict['y1_1'],func_dict['x2_1'],func_dict['y2_1'])
        rectangle2 = (func_dict['x1_2'],func_dict['y1_2'],func_dict['x2_2'],func_dict['y2_2'])
        rectangle3 = (func_dict['x1_3'],func_dict['y1_3'],func_dict['x2_3'],func_dict['y2_3'])
        rectangle4 = (func_dict['x1_4'],func_dict['y1_4'],func_dict['x2_4'],func_dict['y2_4'])
        rectangle5 = (func_dict['x1_5'],func_dict['y1_5'],func_dict['x2_5'],func_dict['y2_5'])
        draw = ImageDraw.Draw(im)
        draw.ellipse(bbox, fill=128)
        draw.rectangle(rectangle1, fill=128)
        draw.rectangle(rectangle2, fill=128)
        draw.rectangle(rectangle3, fill=128)
        draw.rectangle(rectangle4, fill=128)
        draw.rectangle(rectangle5, fill=128)
        del draw
        # im.show()
        pil_image_ellipsed = im

        # Convert RGB to BGR
        img = cv2.cvtColor(np.array(pil_image_ellipsed), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.smallDollarSign1, img, 0.05)

        if not terminalmode: ui_action_and_signals.signal_status.emit("Analysing other players")

        self.PlayerPots = []
        for pt in points:
            if not terminalmode: ui_action_and_signals.signal_progressbar_increase.emit(1)
            x = pt[0] + 9
            y = pt[1] + 1
            modpt = (x, y)
            w = 40
            h = 15
            cv2.rectangle(img, modpt, (x + w, y + h), (0, 0, 255), 2)
            # cv2.imshow("Image",img)
            playerPotImage = pil_image_ellipsed.crop((x, y, x + w, y + h))

            basewidth = 100
            wpercent = (basewidth / float(playerPotImage.size[0]))
            hsize = int((float(playerPotImage.size[1]) * float(wpercent)))
            playerPotImage = playerPotImage.resize((basewidth, hsize), Image.ANTIALIAS)

            playerPotImage = playerPotImage.filter(ImageFilter.MinFilter)

            self.PlayerPots.append(self.get_ocr_float(playerPotImage, 'PlayerPot'))


        try:
            t = [float(x) for x in self.PlayerPots]
            self.playerBetIncreases = [t[i + 1] - t[i] for i in range(len(t) - 1)]
            self.maxPlayerBetIncrease = max(self.playerBetIncreases)

            self.playerBetIncreasesAsPotPercentage = [(x / self.totalPotValue) for x in self.playerBetIncreases]
            self.maxPlayerBetIncreasesAsPotPercentage = max(self.playerBetIncreasesAsPotPercentage)
        except:  # when no other players are around (avoid division by zero)
            self.maxPlayerBetIncrease = 0
            self.playerBetIncreasesAsPotPercentage = [0]
            self.maxPlayerBetIncreasesAsPotPercentage = 0

        try:
            self.playerBetIncreasesPercentage = [t[i + 1] / t[i] for i in range(len(t) - 1)]
            self.maxPlayerBetIncreasesPercentage = max(self.playerBetIncreasesPercentage)

            logger.debug("Player Pots:           " + str(self.PlayerPots))
            logger.debug("Player Pots increases: " + str(self.playerBetIncreases))
            logger.debug("Player increase as %:  " + str(self.playerBetIncreasesPercentage))

        except:
            self.playerBetIncreasesPercentage = [0]
            self.maxPlayerBetIncreasesPercentage = 0
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        if self.isHeadsUp:
            try:
                self.maxPlayerBetIncreasesPercentage = (self.totalPotValue - h.previousPot - h.myLastBet) / h.myLastBet
                self.maxPlayerBetIncrease = (self.totalPotValue - h.previousPot - h.myLastBet) - h.myLastBet
                logger.info("Remembering last bet: " + str(self.myLastBet))
            except:
                logger.debug("Not remembering last bet")
                self.maxPlayerBetIncreasesPercentage = 0
                self.maxPlayerBetIncrease = 0

        # raw_input("Press Enter to continue...")
        # plt.subplot(121),plt.imshow(res)
        # plt.subplot(122),plt.imshow(img,cmap = 'jet')
        # plt.imshow(img, cmap = 'gray', interpolation = 'bicubic')
        # plt.show()


        self.playersBehind = count

        self.playersAhead = int(np.round(self.coveredCardHolders - self.playersBehind))
        logger.debug("Player pots: " + str(self.PlayerPots))

        if p.selected_strategy['smallBlind'] in self.PlayerPots:
            self.playersAhead += 1
            self.playersBehind -= 1
            logger.debug("Found small blind")

        self.playersAhead = int(max(self.playersAhead, 0))
        logger.debug(("Played players: " + str(self.playersBehind)))

        return True

    def get_dealer_position(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        if terminalmode == False: ui_action_and_signals.signal_status.emit("Analyse dealer position")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + 0, self.tlc[1] + 0,
                                    self.tlc[0] +800, self.tlc[1] + 500)

        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.dealer, img, 0.01)
        point=points[0]

        self.position_utg_plus = ''
        for n, fd in enumerate(func_dict, start=0):
            if point[0]>fd[0] and point[1]>fd[1] and point[0]<fd[2] and point[1]<fd[3]:
                self.position_utg_plus=n
                logger.info('Position is UTG+'+str(self.position_utg_plus))

        if self.position_utg_plus=='':
            self.position_utg_plus=0
            logger.error('Could not determine dealer position. Assuming UTG')


        return True

    def get_total_pot_value(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode: ui_action_and_signals.signal_progressbar_increase.emit(5)
        if not terminalmode: ui_action_and_signals.signal_status.emit("Get Pot Value")
        logger.debug("Get TotalPot value")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])

        self.totalPotValue = self.get_ocr_float(pil_image, 'TotalPotValue')

        if self.totalPotValue=='': self.totalPotValue=0
        if self.totalPotValue < 0.01:
            logger.info("unable to get pot value")
            if terminalmode == False: ui_action_and_signals.signal_status.emit("Unable to get pot value")
            time.sleep(1)
            pil_image.save("pics/ErrPotValue.png")
            self.totalPotValue = h.previousPot

        logger.info("Final Total Pot Value: " + str(self.totalPotValue))
        return True

    def get_my_funds(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        logger.debug("Get my funds")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])


        if p.selected_strategy['pokerSite'][0:2]=='PP':
            basewidth = 200
            wpercent = (basewidth / float(pil_image.size[0]))
            hsize = int((float(pil_image.size[1]) * float(wpercent)))
            pil_image = pil_image.resize((basewidth, hsize), Image.ANTIALIAS)
            pil_image_filtered = pil_image.filter(ImageFilter.ModeFilter)
            pil_image_filtered2 = pil_image.filter(ImageFilter.MedianFilter)

        self.myFundsError = False
        try:
            pil_image.save("pics/myFunds.png")
        except:
            logger.info("Could not save myFunds.png")


        self.myFunds = self.get_ocr_float(pil_image, 'MyFunds')

        if self.myFunds == '':
            self.myFundsError = True
            self.myFunds = float(h.myFundsHistory[-1])
            logger.info("myFunds not regognised!")
            if terminalmode == False: ui_action_and_signals.signal_status.emit("!!Funds NOT recognised!!")
            logger.warning("!!Funds NOT recognised!!")
            self.entireScreenPIL.save("pics/FundsError.png")
            time.sleep(0.5)
        logger.info("Funds: " + str(self.myFunds))
        return True

    def get_current_call_value(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode: ui_action_and_signals.signal_status.emit("Get Call value")
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)

        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])

        if not self.checkButton:
            if  p.selected_strategy['pokerSite'][0:2] and self.allInCallButton: self.currentCallValue = ''
            else: self.currentCallValue = self.get_ocr_float(pil_image, 'CallValue')
        elif self.checkButton:
            self.currentCallValue=0


        if self.currentCallValue!='':  self.getCallButtonValueSuccess = True
        else:
            try:
                pil_image.save("pics/ErrCallValue.png")
            except:
                pass


        return True

    def get_current_bet_value(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        if not terminalmode:  ui_action_and_signals.signal_status.emit("Get Bet Value")
        logger.debug("Get bet value")

        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])

        self.currentBetValue = self.get_ocr_float(pil_image, 'BetValue')

        if self.currentCallValue=='' and p.selected_strategy['pokerSite'][0:2] == "PS" and self.allInCallButton:
            logger.warning("Taking call value from button on the right")
            self.currentCallValue = self.currentBetValue
            self.currentBetValue=9999999


        if self.currentBetValue == '':
            logger.warning("No bet value")
            self.currentBetValue = 9999999.0

        if self.currentCallValue=='':
            logger.error("Call Value was empty. ")
            if p.selected_strategy['pokerSite'][0:2] == "PS" and self.allInCallButton:
                self.currentCallValue = self.currentBetValue
                self.currentBetValue=9999999
            try:
                self.entireScreenPIL.save('pics/err_debug_fullscreen.png')
            except:
                pass

            self.currentCallValue=9999999.0

        if self.currentBetValue < self.currentCallValue:
            self.currentCallValue = self.currentBetValue / 2
            self.BetValueReadError = True
            self.entireScreenPIL.save("pics/BetValueError.png")

        logger.info("Final call value: " + str(self.currentCallValue))
        logger.info("Final bet value: " + str(self.currentBetValue))
        return True

    def get_current_pot_value(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        # pil_image.show()
        pil_image.save("pics/currenPotValue.png")
        # blurred = pil_image.filter(ImageFilter.SHARPEN)
        try:
            self.currentRoundPotValue = pytesseract.image_to_string(pil_image, None, False, "-psm 6").replace(" ","").replace("$", "")
        except:
            logger.warning("Error in pytesseract current pot value")

        if len(self.currentRoundPotValue) > 6: self.currentRoundPotValue = ""
        # else: return False

        return True

    def get_lost_everything(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.lostEverything, img, 0.001)
        if count > 0:
            h.lastGameID = str(h.GameID)
            self.myFundsChange = float(0) - float(str(h.myFundsHistory[-1]).strip('[]'))
            L.mark_last_game(t, h)
            if not terminalmode: ui_action_and_signals.signal_status.emit("Everything is lost. Last game has been marked.")
            if not terminalmode: ui_action_and_signals.signal_progressbar_reset.emit()
            #user_input = input("Press Enter for exit ")
            sys.exit()
        else:
            return True

    def get_new_hand(self, mouse):
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        if h.previousCards != self.mycards:
            self.time_new_cards_recognised=time.time()
            h.lastGameID = str(h.GameID)
            h.GameID = int(round(np.random.uniform(0, 999999999), 0))
            cards = ' '.join(self.mycards)
            ui_action_and_signals.signal_status.emit("New hand: " + str(cards))
            L.mark_last_game(t, h)

            t_algo = threading.Thread(name='Algo', target=self.call_genetic_algorithm)
            t_algo.daemon = True
            t_algo.start()

            if not terminalmode: ui_action_and_signals.signal_funds_chart_update.emit(L)
            if not terminalmode: ui_action_and_signals.signal_bar_chart_update.emit(L,p.current_strategy)

            h.myLastBet = 0
            h.myFundsHistory.append(str(self.myFunds))
            h.previousCards = self.mycards
            h.lastSecondRoundAdjustment = 0

            self.take_screenshot(False)
        return True

    def run_montecarlo(self):
        # Prepare for montecarlo simulation to evaluate equity (probability of winning with given cards)

        if self.gameStage == "PreFlop":
            # self.assumedPlayers = self.coveredCardHolders - int(
            #    round(self.playersAhead * (1 - float(p.selected_strategy['CoveredPlayersCallLikelihoodPreFlop'])))) + 1
            self.assumedPlayers = 2

        elif self.gameStage == "Flop":
            self.assumedPlayers = self.coveredCardHolders - int(
                round(self.playersAhead * (1 - float(p.selected_strategy['CoveredPlayersCallLikelihoodFlop'])))) + 1

        else:
            self.assumedPlayers = self.coveredCardHolders + 1

        self.assumedPlayers = min(max(self.assumedPlayers, 2), 3)

        self.PlayerCardList = []
        self.PlayerCardList.append(self.mycards)

        # add cards from colluding players (not yet implemented)
        # col = Collusion()
        # col.
        # if col.got_info==True:
        #     self.PlayerCardList.add

        if self.gameStage == "PreFlop":
            maxRuns=1000 if p.selected_strategy['preflop_override'] else 10000
        else:
            maxRuns = 8000

        if terminalmode == False: ui_action_and_signals.signal_status.emit("Running Monte Carlo: " + str(maxRuns))
        logger.debug("Running Monte Carlo")
        self.montecarlo_timeout = float(config['montecarlo_timeout'])
        timeout = self.timeout_start + self.montecarlo_timeout
        m = MonteCarlo()

        m.run_montecarlo(self.PlayerCardList, self.cardsOnTable, int(self.assumedPlayers), ui, maxRuns=maxRuns, timeout=timeout)
        if terminalmode == False: ui_action_and_signals.signal_status.emit("Monte Carlo completed successfully")
        logger.debug("Monte Carlo completed successfully with runs: " + str(m.runs))

        self.equity = np.round(m.equity, 3)
        self.winnerCardTypeList = m.winnerCardTypeList

        ui_action_and_signals.signal_progressbar_increase.emit(30)

class TablePartyPoker(TableScreenBased):
    def get_covered_card_holders(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        if terminalmode == False: ui_action_and_signals.signal_status.emit("Analyse other players and position")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])
        if not terminalmode: ui_action_and_signals.signal_status.emit("Analysing other players")

        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.coveredCardHolder, img, func_dict['tolerance'])
        self.coveredCardHolders = np.round(count)
        logger.info("Covered cardholders (number of other players ex luding myself): " + str(self.coveredCardHolders))

        if self.coveredCardHolders == 1:
            self.isHeadsUp = True
            logger.debug("HeadSUP detected!")
        else:
            self.isHeadsUp = False

        self.PlayerNames = []
        self.PlayerFunds = []

        if self.coveredCardHolders == 0:
            logger.error("No other players found. Assuming 1 player")
            self.coveredCardHolders = 1

        return True

    def get_played_players(self):
        func_dict = self.coo[inspect.stack()[0][3]][self.tbl]
        if not terminalmode:  ui_action_and_signals.signal_progressbar_increase.emit(5)
        if terminalmode == False: ui_action_and_signals.signal_status.emit("Analyse past players")
        pil_image = self.crop_image(self.entireScreenPIL, self.tlc[0] + func_dict['x1'], self.tlc[1] + func_dict['y1'],
                                    self.tlc[0] + func_dict['x2'], self.tlc[1] + func_dict['y2'])

        # Convert RGB to BGR
        img = cv2.cvtColor(np.array(pil_image), cv2.COLOR_BGR2RGB)
        count, points, bestfit = self.find_template_on_screen(self.smallDollarSign1, img, 0.01)

        if not terminalmode: ui_action_and_signals.signal_status.emit("Checking for played players")
        self.playersBehind = count

        self.PlayerPots = []
        for pt in points:
            if not terminalmode: ui_action_and_signals.signal_progressbar_increase.emit(1)
            x1 = pt[0] + 7 +self.tlc[0]
            y1 = pt[1] + 1 +self.tlc[1]
            x2=x1+ 40
            y2=y1+ 15
            player_pot_image = self.crop_image(self.entireScreenPIL, x1,y1,x2,y2)
            self.PlayerPots.append(self.get_ocr_float(player_pot_image, 'PlayerPot'))
            self.PlayerPots=sorted(self.PlayerPots)
            player_pot_diff = np.diff(self.PlayerPots)

            self.playersAhead = self.coveredCardHolders - self.playersBehind

        return True

class ThreadManager(threading.Thread):
    def __init__(self, threadID, name, counter):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.counter = counter

    def update_most_gui_items(self):
        if terminalmode == False:
            ui_action_and_signals.signal_decision.emit(d.decision)
            ui_action_and_signals.signal_status.emit(d.decision)

            ui_action_and_signals.signal_lcd_number_update.emit('equity', np.round(t.equity * 100, 2))
            ui_action_and_signals.signal_lcd_number_update.emit('required_minbet', t.currentBetValue)
            ui_action_and_signals.signal_lcd_number_update.emit('required_mincall', t.minCall)
            #ui_action_and_signals.signal_lcd_number_update.emit('potsize', t.totalPotValue)
            ui_action_and_signals.signal_lcd_number_update.emit('gamenumber', int(L.get_game_count(p.current_strategy)))
            ui_action_and_signals.signal_lcd_number_update.emit('assumed_players', int(t.assumedPlayers))
            ui_action_and_signals.signal_lcd_number_update.emit('calllimit', d.finalCallLimit)
            ui_action_and_signals.signal_lcd_number_update.emit('betlimit', d.finalBetLimit)
            #ui_action_and_signals.signal_lcd_number_update.emit('zero_ev', round(d.maxCallEV, 2))

            ui_action_and_signals.signal_pie_chart_update.emit(t.winnerCardTypeList)
            ui_action_and_signals.signal_curve_chart_update1.emit(h.histEquity, h.histMinCall, h.histMinBet, t.equity,
                                                                  t.minCall, t.minBet,
                                                                  'bo',
                                                                  'ro')

            ui_action_and_signals.signal_curve_chart_update2.emit(t.power1, t.power2, t.minEquityCall, t.minEquityBet,
                                                                  t.smallBlind, t.bigBlind,
                                                                  t.maxValue,
                                                                  t.maxEquityCall, t.maxEquityBet)

    def run(self):
            global h, L, p, t, d, terminalmode
            h = History()

            while True:
                if p.pause:
                    while p.pause == True:
                        time.sleep(1)
                        if p.exit_thread == True: sys.exit()

                p.read_strategy()
                if p.selected_strategy['pokerSite'][0:2] == "PS":
                    t = TablePartyPoker()
                    mouse = MouseMoverTableBased(p.selected_strategy['pokerSite'])
                elif p.selected_strategy['pokerSite'] == "PP":
                    t = TableScreenBased()
                    mouse = MouseMoverTableBased(p.selected_strategy['pokerSite'])
                elif p.selected_strategy['pokerSite'] == "F1":
                    # t = TableF1()
                    logger.critical("Pokerbot tournament not yet supported")
                    exit()

                ready = False
                while (not ready):
                    ready = t.take_screenshot(True) and \
                            t.get_top_left_corner() and \
                            t.check_for_captcha(mouse) and \
                            t.get_lost_everything() and \
                            t.check_for_imback(mouse) and \
                            t.get_my_funds() and \
                            t.get_my_cards() and \
                            t.get_new_hand(mouse) and \
                            t.check_for_button() and \
                            t.get_table_cards() and \
                            t.get_covered_card_holders() and \
                            t.get_total_pot_value() and \
                            t.get_dealer_position() and \
                            t.get_played_players() and \
                            t.check_for_checkbutton() and \
                            t.check_for_call() and \
                            t.check_for_allincall() and \
                            t.get_current_call_value() and \
                            t.get_current_bet_value()

                if not p.pause:
                    t.run_montecarlo()
                    d = Decision(t, h, p, logger, L)
                    d.make_decision(t, h, p, logger, L)

                    if p.exit_thread: sys.exit()

                    self.update_most_gui_items()

                    logger.info(
                        "Equity: " + str(t.equity * 100) + "% -> " + str(int(t.assumedPlayers)) + " (" + str(
                            int(t.coveredCardHolders)) + "-" + str(int(t.playersAhead)) + "+1) Plr")

                    logger.info("Final Call Limit: " + str(d.finalCallLimit) + " --> " + str(t.minCall))

                    logger.info("Final Bet Limit: " + str(d.finalBetLimit) + " --> " + str(t.currentBetValue))

                    logger.info("Pot size: " + str((t.totalPotValue)) + " -> Zero EV Call: " + str(round(d.maxCallEV, 2)))

                    logger.info("+++++++++++++++++++++++ Decision: " + str(d.decision) + "+++++++++++++++++++++++")

                    mouse = MouseMoverTableBased(p.selected_strategy['pokerSite'], p.selected_strategy['BetPlusInc'], t.currentBluff)
                    mouse_target=d.decision
                    if mouse_target=='Call' and t.allInCallButton:
                        mouse_target='Call2'
                    mouse.mouse_action(mouse_target, t.tlc, logger)

                    t.time_action_completed = time.time()

                    if terminalmode == False: ui_action_and_signals.signal_status.emit("Writing log file")

                    L.write_log_file(p, h, t, d)

                    h.previousPot = t.totalPotValue
                    h.histGameStage = t.gameStage
                    h.histDecision = d.decision
                    h.histEquity = t.equity
                    h.histMinCall = t.minCall
                    h.histMinBet = t.minBet
                    h.histPlayerPots = t.PlayerPots


# ==== MAIN PROGRAM =====
if __name__ == '__main__':
    print ("This is a testversion and error messages will appear here. The user interface has opened in a separate window.")
    # Back up the reference to the exceptionhook
    sys._excepthook = sys.excepthook
    u=UpdateChecker()
    u.check_update(version)

    def my_exception_hook(exctype, value, traceback):
        # Print the error and traceback
        print(exctype, value, traceback)
        # Call the normal Exception hook after
        sys._excepthook(exctype, value, traceback)
        sys.exit(1)

    # Set the exception hook to our wrapping function
    sys.excepthook = my_exception_hook

    # check for tesseract
    try:
        pytesseract.image_to_string(Image.open('pics/PP/3h.png'))
    except Exception as e:
        print (e)
        print ("Tesseract not installed. Please install it into the same folder as the pokerbot or alternatively set the path variable.")
        #subprocess.call(["start", 'tesseract-installer/tesseract-ocr-setup-3.05.00dev.exe'], shell=True)
        sys.exit()

    config = ConfigObj("config.ini")
    try:
        terminalmode = int(config['terminalmode'])
    except:
        terminalmode=0

    logger = debug_logger().start_logger()

    p = StrategyHandler()
    p.read_strategy()

    L = GameLogger()

    if not terminalmode:
        p.exit_thread=False
        p.pause=True
        app = QtWidgets.QApplication(sys.argv)
        MainWindow = QtWidgets.QMainWindow()
        ui = Ui_Pokerbot()
        ui.setupUi(MainWindow)

        ui_action_and_signals = UIActionAndSignals(ui, p, L, logger)
        t1 = ThreadManager(1, "Thread-1", 1)
        t1.start()

        MainWindow.show()
        try:
            sys.exit(app.exec_())
        except:
            print("Preparing to exit...")
            p.exit_thread = True

    elif terminalmode:
        print("Terminal mode selected. To view GUI set terminalmode=False")
        t1 = ThreadManager(1, "Thread-1", 1)
        t1.start()
