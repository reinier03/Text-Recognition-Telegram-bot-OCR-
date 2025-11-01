from DeeperSeek import DeepSeek
from logging import *
import zendriver
from zendriver.core.element import Element
import os
import platform
from asyncio.events import get_event_loop
from DeeperSeek.internal.exceptions import *
from DeeperSeek.internal.objects import Optional, Response
from typing import Optional, List
import time
from bs4 import BeautifulSoup
from inscriptis import get_text
from re import match
from config import *
import asyncio
import json
import requests
import telebot
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class DeeplySeeking(DeepSeek):

    def __init__(self, token = None , email = None, password = None, chat_id = None, headless = True, verbose = 
    False, chrome_args = ..., attempt_cf_bypass = True, android = True):
        super().__init__(token, email, password, chat_id, headless, verbose, chrome_args, attempt_cf_bypass)

        self.android = android

        # contenedor de respuestas de deepseek -> div._4f9bf79
        # tres puntos de generacion de respuesta -> div.b4e4476b.febb9909

        #selectores que hay que modificar ya que no funcionan...
        self.selectors.interactions.textbox = "textarea"
        self.selectors.interactions.send_button = "div.ds-icon-button._7436101"
        self.selectors.backend.response_generating = "div.b4e4476b.febb9909"
        self.selectors.backend.response_generated = "div._4f9bf79"
        self.selectors.interactions.response_toolbar = "div.ds-flex._965abe9._54866f7"
        

    async def initialize(self, language: str = "en") -> None:
        """Initializes the DeepSeek session.

        This method sets up the logger, starts a virtual display if necessary, and launches the browser.
        It also navigates to the DeepSeek chat page and handles the login process using either a token
        or email and password.

        Raises
        ---------
        ValueError:
            PyVirtualDisplay is not installed.
        ValueError:
            Xvfb is not installed.
        """

        
            

        if language == "es":
            language = "es-ES"

        else:
            language = "en-UK"


        # Initilize the logger
        self.logger = getLogger("DeeperSeek")
        self.logger.setLevel(DEBUG)

        if self._verbose:
            handler = StreamHandler()
            handler.setFormatter(Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%H:%M:%S"))
            self.logger.addHandler(handler)

        # Start the virtual display if the system is Linux and the DISPLAY environment variable is not set
        if platform.system() == "Linux" and "DISPLAY" not in os.environ:
            self.logger.debug("Starting virtual display...")
            try:
                from pyvirtualdisplay.display import Display
                self.display = Display()
                self.display.start()
            except ModuleNotFoundError:
                raise ValueError(
                    "Please install PyVirtualDisplay to start a virtual display by running `pip install PyVirtualDisplay`"
                )
            except FileNotFoundError as e:
                if "No such file or directory: 'Xvfb'" in str(e):
                    raise ValueError(
                        "Please install Xvfb to start a virtual display by running `sudo apt install xvfb`"
                    )
                raise e

        # Start the browser
        if self.android:
            
            if os.name != "nt":
                self.browser = await zendriver.start(
                    chrome_args = self._chrome_args,
                    user_agent="--user-agent=Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.116 Mobile Safari/537.36",
                    browser_args=["--window-size=450,851", "--window-position=0,0", "--lang={}".format(language) ,"--accept-lang={}".format(language), "--headless=new", "--disable-dev-shm-usage", "--disable-gpu"]
                )

            else:
                self.browser = await zendriver.start(
                    chrome_args = self._chrome_args,
                    headless = self._headless,
                    user_agent="--user-agent=Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.116 Mobile Safari/537.36",
                    browser_args=["--window-size=450,851", "--window-position=0,0", "--lang={}".format(language) ,"--accept-lang={}".format(language)]
                )

        else:
            self.browser = await zendriver.start(
                chrome_args = self._chrome_args,
                headless = self._headless,
                user_agent="--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, como Gecko) Chrome/135.0.0.0 Safari/537.36",
                browser_args=["--window-position=0,0", "--lang={}".format(language) ,"--accept-lang={}".format(language)]
            )


        self.logger.debug("Navigating to the chat page...")
        await self.browser.get("https://chat.deepseek.com/" if not self._chat_id \
            else f"https://chat.deepseek.com/a/chat/s/{self._chat_id}")

        if self._attempt_cf_bypass:
            try:
                self.logger.debug("Verifying the Cloudflare protection...")
                await self.browser.main_tab.verify_cf()
            except: # It times out if there was no need to verify
                pass
        
        self._initialized = True
        self._is_active = True
        loop = get_event_loop()
        loop.create_task(self._keep_alive())
        
        try:
            if self._token:
                if os.name == "nt":
                    await self._login(timeout=100)
                else:
                    await self._login(30)
            else:
                await self._login_classic(timeout=100)

        except:
            pass


    async def _login(self, timeout: int = 5) -> None:
        """Logs in to DeepSeek using a token.

        This method sets the token in the browser's local storage and reloads the page to authenticate.
        If the token is invalid, it falls back to the classic login method. (email and password)

        Raises
        ---------
            MissingInitialization: If the initialize method is not run before using this method.
        """

        if not self._initialized:
            raise MissingInitialization("You must run the initialize method before using this method.")

        self.logger.debug("Logging in using the token...")
        await self.browser.main_tab.evaluate(
            f"localStorage.setItem('userToken', JSON.stringify({{value: '{self._token}', __version: '0'}}))",
            await_promise = True,
            return_by_value = True
        )
        await self.browser.main_tab.reload()
        
        # Reloading with an invalid token still gives access to the website somehow, but only for a split second
        # So I added a delay to make sure the token is actually invalid
        await asyncio.sleep(2)
        
        # Check if the token login was successful
        try:
            await self.browser.main_tab.wait_for(self.selectors.interactions.textbox, timeout = timeout)
        except:
            self.logger.debug("Token failed, logging in using email and password...")

            if self._email and self._password:
                return await self._login_classic(token_failed = True)
            else:
                raise InvalidCredentials("The token is invalid and no email or password was provided")

        self.logger.debug("Token login successful!")
        
    async def _login_classic(self, token_failed: bool = False, timeout: int = 5) -> None:
        """Logs in to DeepSeek using email and password.

        Args
        ---------
            token_failed (bool): Indicates whether the token login attempt failed.
        
        Raises:
        ---------
            MissingInitialization: If the initialize method is not run before using this method.
            InvalidCredentials: If the email or password is incorrect.
        """

        if not self._initialized:
            raise MissingInitialization("You must run the initialize method before using this method.")

        self.logger.debug("Entering the email and password...")
        email_input = await self.browser.main_tab.select(self.selectors.login.email_input)
        await email_input.send_keys(self._email)

        password_input = await self.browser.main_tab.select(self.selectors.login.password_input)
        await password_input.send_keys(self._password)

        self.logger.debug("Checking the confirm checkbox and logging in...")
        confirm_checkbox = await self.browser.main_tab.select(self.selectors.login.confirm_checkbox)
        await confirm_checkbox.click()

        login_button = await self.browser.main_tab.select(self.selectors.login.login_button)
        await login_button.click()

        try:
            await self.browser.main_tab.wait_for(self.selectors.interactions.textbox, timeout = timeout)
        except:
            raise InvalidCredentials("The email or password is incorrect" \
                if not token_failed else "Both token and email/password are incorrect")

        self.logger.debug(f"Logged in successfully using email and password! {'(Token method failed)' if token_failed else ''}")

    async def send_message(
        self,
        message: str,
        pre_message: str = None, #this one it's for a pre instruccion in every message about how to proceed
        slow_mode: bool = False,
        deepthink: bool = False,
        search: bool = False,
        timeout: int = 60,
        slow_mode_delay: float = 0.25
    ) -> Optional[Response]: 
        """
        Takes control of the captcha
        """
        if pre_message:
            message = str(pre_message) + "\n\n" + str(message)

        try:
            return await self._send_message(message, slow_mode, deepthink, search, timeout, slow_mode_delay)
        except Exception as err:
            await self.browser.main_tab.find("you are human")
            await self.browser.main_tab.reload()
            return await self._send_message(message, slow_mode, deepthink, search, timeout, slow_mode_delay)
            


            

    async def _send_message(
        self,
        message: str,
        slow_mode: bool = False,
        deepthink: bool = False,
        search: bool = False,
        timeout: int = 60,
        slow_mode_delay: float = 0.25
    ) -> Optional[Response]:
        """Sends a message to the DeepSeek chat.

        Args
        ---------
            message (str): The message to send.
            slow_mode (bool): Whether to send the message character by character with a delay.
            deepthink (bool): Whether to enable deepthink mode.
                - Setting this to True will add 20 seconds to the timeout.
            search (bool): Whether to enable search mode.
                - Setting this to True will add 60 seconds to the timeout.
            timeout (int): The maximum time to wait for a response.
                - Sometimes a response may take longer than expected, so it's recommended to increase the timeout if necessary.
                - Do note that the timeout increases by 20 seconds if deepthink is enabled, and by 60 seconds if search is enabled.
            slow_mode_delay (float): The delay between sending each character in slow mode.

        Returns
        ---------
            Optional[Response]: The generated response from DeepSeek, or None if no response is received within the timeout

        Raises
        ---------
            MissingInitialization: If the initialize method is not run before using this method.
        """

        if not self._initialized:
            raise MissingInitialization("You must run the initialize method before using this method.")
        


        timeout += 20 if deepthink else 0
        timeout += 60 if search else 0

        self.logger.debug(f"Finding the textbox and sending the message: {message}")
        textbox = await self.browser.main_tab.select("textarea")
        if slow_mode:
            for char in message:
                await textbox.send_keys(char)
                await asyncio.sleep(slow_mode_delay)
        else:
            await textbox.send_keys(message)

        # Find the parent div of both deepthink and search options
        send_options_parent = await self.browser.main_tab.select(self.selectors.interactions.send_options_parent)
        
        if deepthink != self._deepthink_enabled:
            await send_options_parent.children[0].click() # DeepThink (R1)
            self._deepthink_enabled = deepthink
        
        if search != self._search_enabled:
            await send_options_parent.children[1].click() # Search
            self._search_enabled = search

        try:
            ai_responses = await self.browser.main_tab.select_all(self.selectors.backend.response_generated)
        except:
            ai_responses = None

        if not self.android:
            text = await self.browser.main_tab.select(self.selectors.interactions.textbox)
            await text.send_keys(zendriver.SpecialKeys.ENTER)

        else:
            button = await self.browser.main_tab.select("div[class='bf38813a']")
            button = button.children[-1]
            await button.click()

        return await self._get_response(ai_responses, timeout = timeout)
    
    async def _get_response(
        self,
        ai_responses: List[Element] | None,
        timeout: int = 60,
        regen: bool = False,
    ) -> Optional[Response]:
        """Waits for and retrieves the response from DeepSeek.

        Args
        ---------
            timeout (int): The maximum time to wait for the response.
            regen (bool): Whether the response is a regenerated response.

        Returns
        ---------
            Optional[Response]: The generated response from DeepSeek, or None if no response is received within the timeout.
        
        Raises
        ---------
            MissingInitialization: If the initialize method is not run before using this method.
            ServerDown: If the server is busy and the response is not generated.
        """


        if not self._initialized:
            raise MissingInitialization("You must run the initialize method before using this method.")

        end_time = time.time() + timeout


        # Wait till the response starts generating
        # If we don't wait for the response to start re/generating, we might get the previous response
        self.logger.debug("Waiting for the response to start generating..." if not regen \
            else "Waiting for the response to start regenerating...")
        while time.time() < end_time:
            try:
                #in case the answer it's generated so quickly that the element dosen't shows up...
                elements_in_dom = await self.browser.main_tab.select_all(self.selectors.interactions.response_toolbar)
                if len(elements_in_dom) > (len(ai_responses) if ai_responses else 0):
                    break

                _ = await self.browser.main_tab.select(self.selectors.backend.response_generating if not regen \
                    else self.selectors.backend.regen_loading_icon)
            except:
                continue
            else:
                break
        
        if time.time() >= end_time:
            return None

        # Once the response starts generating, wait till it's generated
        response_generated = None
        self.logger.debug("Waiting for the response to finish generating..." if not regen \
            else "Finding the last response...")
        while time.time() < end_time:
            try:
                # toolbar message downside -> div.ds-flex._965abe9._54866f7
                #in case the answer it's generated so quickly that the element dosen't shows up...
                elements_in_dom = await self.browser.main_tab.select_all(self.selectors.interactions.response_toolbar)
                if len(elements_in_dom) > (len(ai_responses) if ai_responses else 0):
                    
                    response_generated: zendriver.Element = await self.browser.main_tab.select_all(
                        self.selectors.backend.response_generated)
                    
                else:
                    continue

            except:
                continue

            if response_generated:
                break


        if not response_generated:
            return None


        if regen:
            # Wait till toolbar appears
            self.logger.debug("Waiting for the response toolbar to appear...")
            while time.time() < end_time:
                # I need to keep refreshing the response_generated list because the elements change
                try:
                    response_generated: zendriver.Element = await self.browser.main_tab.select_all(
                        self.selectors.backend.response_generated)
                except Exception as e:
                    continue

                # Check if the toolbar is present
                soup = BeautifulSoup(repr(response_generated[-1]), 'html.parser')
                toolbar = soup.find("div", class_ = self.selectors.backend.response_toolbar_b64)
                if not toolbar:
                    continue

                response_generated = await self.browser.main_tab.select_all(self.selectors.backend.response_generated)
                break
            
            if time.time() >= end_time:
                return None

        self.logger.debug("Extracting the response text...")
        soup = BeautifulSoup(repr(response_generated[-1].children[0]), 'html.parser')
        markdown_blocks = soup.find_all("div", class_ = "ds-markdown")
        response_text = "\n\n".join([i.text for i in markdown_blocks[-1].find_all("span")]) #if there is 2, the first one it's the deepthink and the second one it's the text

        if response_text.lower() == "the server is busy. please try again later.":
            raise ServerDown("The server is busy. Please try again later.")

        search_results = None
        deepthink_duration = None
        deepthink_content = None

        #I put this on a conditional becouse i won't use for my project and i don't have time to fix it. just make sure that you don't pass True to the arguments
        if self._deepthink_enabled or self._search_enabled:
            # 1 and 2 are the deepthink and search options
            for child in response_generated[-1].children[1:3]:
                if (match(r"found \d+ results", child.text.lower()) or match(r"Read \d+ web pages", child.text.lower())) and self._search_enabled:
                    self.logger.debug("Extracting the search results...")
                    # So this is a search result option, we need to click it and find the search results div
                    await child.click()

                    search_results = await self.browser.main_tab.select_all(self.selectors.interactions.search_results)
                    # First child is "Search Results". Second child is the actual search results
                    search_results_children = search_results[-1].children[1].children

                    search_results = self._filter_search_results(search_results_children)
                
                if match(r"thought for \d+(\.\d+)? seconds", child.text.lower()) and self._deepthink_enabled:
                    self.logger.debug("Extracting the deepthink duration and content...")
                    # This is the deepthink option, we can find the duration through splitting the text
                    deepthink_duration = int(child.text.split()[2])
                    
                    # DeepThink content is shown by default, no need to click anything
                    deepthink_content = await self.browser.main_tab.select_all(self.selectors.interactions.deepthink_content)
                    soup = BeautifulSoup(repr(deepthink_content[-1]), 'html.parser')
                    deepthink_content = "\n".join(get_text(str(p)).strip() for p in soup.find_all('p'))

        response = Response(
            text = response_text,
            chat_id = self._chat_id,
            deepthink_duration = deepthink_duration,
            deepthink_content = deepthink_content,
            search_results = search_results
        )
        
        self.logger.debug("Response generated!")
        return response





