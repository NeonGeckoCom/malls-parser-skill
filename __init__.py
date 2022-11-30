# NEON AI (TM) SOFTWARE, Software Development Kit & Application Framework
# All trademark and other rights reserved by their respective owners
# Copyright 2008-2022 Neongecko.com Inc.
# Contributors: Daniel McKnight, Guy Daniels, Elon Gasper, Richard Leeds,
# Regina Bloomstine, Casimiro Ferreira, Andrii Pernatii, Kirill Hrymailo
# BSD-3 License
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 3. Neither the name of the copyright holder nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO,
# THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS;  OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE,  EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from neon_utils.skills.neon_skill import NeonSkill, LOG
from mycroft.skills.core import intent_file_handler
from .request_handling import existing_lang_check, get_store_data, \
    store_selection_by_floors, \
    location_format, \
    curent_time_extraction
import re
from lingua_franca.format import nice_duration


class DirectorySkill(NeonSkill):

    def __init__(self):
        super(DirectorySkill, self).__init__(name="DirectorySkill")
        self.url = "https://www.alamoanacenter.com/en/directory/"
        self._speak_timeout = 60

    @property
    def request_lang(self):
        return self.lang.split('-')[0]

    def initialize(self):
        # When first run or prompt not dismissed, wait for load and prompt user
        if self.settings.get('prompt_on_start'):
            self.bus.once('mycroft.ready', self._start_mall_parser_prompt)

    @intent_file_handler("run_mall_parser.intent")
    def start_mall_parser_intent(self, message):
        LOG.info(message.data)
        self._start_mall_parser_prompt(message)
        return

    # @property
    def mall_link(self):
        mall_link = 'https://www.alamoanacenter.com/'
        return self.settings.get("mall_link") or mall_link

    def user_request_handling(self, message):
        """
        Checks user language existence on mall's web-page
        using existing_lang_check() function.
        Returns:
            None, None: if message is empty
            None, None: if language is not supported
            user_request, link (str, str): if language exists
            answer)
        """
        LOG.info(f"Message is {message.data}")
        if message.data == {} or message is None:
            return None, None
        else:
            user_request = message.data['store']
            LOG.info(f"{self.mall_link()}")
            LOG.info(str(self.request_lang))
            LOG.info(user_request)
            found, link = existing_lang_check(self.request_lang, self.mall_link())
            if found:
                link = self.mall_link() + self.request_lang + '/directory/'
                LOG.info('new link: ' + link)
                return user_request, link
            else:
                self.speak_dialog("no_lang")
                return None, None

    def start_again(self):
        """
        Asks yes/no question whether user wants to
        get another store info, after Neon gave the
        information about previously selected store.
        If user's answer 'yes': asks what store is
        needed. Returns user's answer.
        If 'no', speaks corresponding dialog.
        If some other answer, speaks corresponding
        dialog
        Returns:
            None (if no store in request, if user's
            answer is 'no', if user gives some other
            answer)
        """
        start_again = self.ask_yesno("ask_more")
        if start_again == "yes":
            another_store = self.get_response('another_store')
            if another_store is not None:
                LOG.info(f'another store {another_store}')
                return another_store
        elif start_again == "no":
            self.speak_dialog('no_store_request')
        else:
            self.speak_dialog('unexpected_error')
        return None

    def speak_stores(self, store_info):
        """
        Speaks store info that was found.
        Substitutes time format for better pronunciation.
        speak_dialog('found_store', {"name": store['name'], "hours": hours, "location": location})
        Shows store label image in gui.
        Args:
            store_info (list): found stores on user's
                                request
        """
        for store in store_info:
            LOG.info(store)
            location = location_format(store['location'])
            hours = re.sub('(\d+)\:*(\d*)am.+(\d+)pm', r'from \1 \2 A M to \3 P M', store['hours'])
            LOG.info(f'changed hours {hours}')
            self.speak_dialog('found_store', {"name": store['name'], "hours": hours, "location": location})
            LOG.info({"name": store['name'], "hours": hours, "location": location})
            self.gui.show_image(store['logo'], caption=f'{hours} {location}', title=store['name'])

    def location_selection(self, store_info):
        """
        If there are several stores in found stores list
        and user wants to get store info on the certain
        floor. If store on that floor exists speaks
        this store info. Else speaks all stores info.
        Args:
            store_info (list): found stores on user's
                                request
        Returns:
            3, None (to ask for another store info)
        """
        LOG.info(f"store by location selection {store_info}")
        floor = self.get_response('which_floor')
        stores = store_selection_by_floors(floor, store_info)
        if stores:
            self.speak_stores(stores)
        else:
            self.speak_dialog('no_store_on_level')
            self.speak_stores(store_info)
        return 3, None

    def open_stores_search(self, store_info, day_time, hour, min):
        """
       Selects open stores. Collects the list of
       open stores else return empty list.
       Args:
           store_info (list): found stores on user's
                               request
       Returns:
           store_info (list): open stores
       """
        open_stores = []
        LOG.info(f'users_time {day_time, hour, min}')
        for store in store_info:
            formated_work_time = self.time_normalization(store['hours'])
            LOG.info(f'formated_work_time {formated_work_time}')
            if day_time[1] == 'am' and formated_work_time[0][0] <= hour:
                if formated_work_time[0][1] > min:
                    open_stores.append(store)
            elif day_time[1] == 'pm' and formated_work_time[1][0] == hour:
                if formated_work_time[1][1] > min:
                    open_stores.append(store)
            elif day_time[1] == 'pm' and formated_work_time[1][0] > hour:
                open_stores.append(store)
        LOG.info(f'open stores {open_stores}')            
        return open_stores

    def time_normalization(self, work_time):
        parse_time = re.findall(r'(\d+\:*\d*)+', work_time)

        open_hour_mins = re.findall(r'(\d+)', parse_time[0])
        open_hour = int(open_hour_mins[0])
        if len(open_hour_mins) > 1:
            open_minutes = int(open_hour_mins[1])
        else: 
            open_minutes = 0

        close_hour_mins = re.findall(r'(\d+)', parse_time[1])
        close_hour = int(close_hour_mins[0])
        if len(close_hour_mins) > 1:
            close_minutes = int(close_hour_mins[1])
        else: 
            close_minutes = 0
        return ([open_hour, open_minutes], [close_hour, close_minutes])

    def time_calculation(self, store_info, open, day_time, hour, min):
        """
        Calculates time difference between user's current time
        and store working hours.
        If 'open' argument is True:
            If user one hour or less before closing: speaks how
                many minutes left. Speaks store info.
            Else speaks corresponging dialog.
            Speaks store info.
        If 'closed' argument is False:
            Speaks corresponding dialog.
            If user is one hour or less before opening hours
                speaks how much time is left for waiting.
            If user's time is 'am' and user is before opening
                hours, speaks how many hours and minutes left
                waiting.
            If user's time is evening (pm) speaks when the store
                opens in the morning.
                Speaks store info.
        Args:
            store_info (list): found stores on user's request
            open (boolean): True - if store is open
            day_time (str): user's current day time (am|pm)
            hour (int): user's current hour
            min (int): user's current minute
        Returns:
            3, None (to ask for another store info)
        Examples:
            work time 9am-10pm
            user's time 8am
            Prompt: 'store is closed now. Opens in 1 hour'
        """
        for store in store_info:
            work_time = store['hours']
            store_name = store['name']
            LOG.info(f'Store work time  {work_time}')
            normalized_time = self.time_normalization(work_time)
            LOG.info(f'Normalixed time {normalized_time}')
            # time left
            wait_h_opening = normalized_time[0][0] - hour
            wait_min_opening = normalized_time[0][1] - min 

            wait_h_closing = normalized_time[1][0] - hour
            wait_min_closing = normalized_time[1][1] - min
            LOG.info(f'wait_h_closing {wait_h_closing}')
            LOG.info(f'wait_min_closing {wait_min_closing}')
            LOG.info(f'day_time {day_time[1]}')
            if open:
                duration = None
                if day_time[1] == 'pm':
                    if 0 == wait_h_closing and wait_min_closing > 0:
                        duration = wait_min_closing * 60
                    elif wait_h_closing == 1 and wait_min_closing < 0:
                        wait_min_closing = 60 - min
                        duration = wait_min_closing * 60
                    elif wait_h_closing == 1 and wait_min_closing == 0:
                        duration = 60 * 60
                if duration:
                    formated_duration = nice_duration(duration, lang=str(self.request_lang), speech=True)
                    LOG.info(f'{store_name} closes in {formated_duration}.')
                    self.speak_dialog('time_before_closing', {"store_name": store_name, "duration": formated_duration})
                else:
                    LOG.info(f'{store_name} is open.')
                    self.speak_dialog('open_now', {'store_name': store_name})
                self.speak_stores([store])
            else:
                if day_time[1] == 'am':
                    duration = wait_h_opening * 3600 + wait_min_opening * 60
                    formated_duration = nice_duration(duration, lang=str(self.request_lang), speech=True)
                    LOG.info(f'{store_name} is closed now. store opens in {formated_duration}')
                    self.speak_dialog('waiting_for_opening', {"store_name": store_name, 'duration': formated_duration})
                else:
                    open_time = work_time.split(' – ')[0]
                    open_time = re.sub('(\d+)\:*(\d*)am', r'\1 \2 A M', open_time)
                    LOG.info(f'{store_name} is closed now. store opens at {open_time}')
                    self.speak_dialog('closed_now', {'store_name': store_name, 'open_time': open_time})
                self.speak_stores([store])
        return 3, None

    def stores_by_time_selection(self, store_info):
        """
        If user chose to select stores by time or
        use like default selection. Gets user's
        current time. Selects open stores.
        Args:
           store_info (list): found stores on user's
                               request
        Returns:
            time_calculation function with True
                in 'open' argument.
            time_calculation function with False
                in 'open' argument. (if list
                of open stores is 0)

        """
        LOG.info(f"store by time selection {store_info}")
        #day_time, hour, min = curent_time_extraction()
        day_time, hour, min = ['7:55', 'pm'], 7, 55
        open_stores = self.open_stores_search(store_info, day_time, hour, min)
        if len(open_stores) >= 1:
            return self.time_calculation(open_stores, True, day_time, hour, min)
        else:
            return self.time_calculation(store_info, False, day_time, hour, min)

    def find_store(self, user_request, mall_link):
        """
        When the intent is matched, user_request
        variable contains the name of the store.
        The matching function get_store_data() is
        used to find the store name in cache or
        on the mall page.
        If user's request is not None this function
        can return several stores, one store or empty
        list.
        If no store was found asks user to repeat.
        returns 1, user_request to continue the
        execution loop in self.execute().
        If there are several stores asks user what way
        of sorting to choose: time, level, nothing.
            If 'time' - finds open stores. If open stores
            list is not empty speaks open stores, else
            tells time difference between user and stores'
            work hours.
            If 'location' - asks what level user is interested
            in. If stores were found speaks stores' info,
            else tells that there is no store on that level
            and speaks all found stores.
            If  'no' - sorts by time.
            If nothing matched in the answer - sorts by time.
        If there was one store found speaks this
        store info. Returns 3, None to stop current
        store search.
        Location and time sorting functions return
        3, None to stop current store search.
        """
        LOG.info(f'user_request {user_request}')
        LOG.info(f'mall_link {mall_link}')
        if user_request is not None:
            self.speak_dialog("start_parsing")
            LOG.info(f"I am parsing stores and malls for your request")
            file_path = self.file_system.path
            LOG.info(f'file_path {file_path}')
            store_info = get_store_data(mall_link, user_request, file_path)
            LOG.info(f"I found {len(store_info)} stores")
            LOG.info(f"store list: {store_info}")
            if len(store_info) == 0:
                user_request = self.get_response('store_not_found', {"store_name": user_request})
                return 1, user_request
            elif len(store_info) > 1:
                self.speak_dialog('more_than_one')

                # ask for the way of selection: time, location, nothing
                sorting_selection = self.get_response('choose_selection')
                if sorting_selection:
                    LOG.info(f'Users answer on sorting options: {sorting_selection}')
                    if self.voc_match(sorting_selection, "time"):
                        LOG.info('Time sorting selected')
                        return self.stores_by_time_selection(store_info)
                    elif self.voc_match(sorting_selection, "location"):
                        LOG.info('Location sorting selected')
                        return self.location_selection(store_info)
                    elif self.voc_match(sorting_selection, "no"):
                        LOG.info('No sorting selected. Sorting by time on default.')
                        return self.stores_by_time_selection(store_info)
                    else:
                        LOG.info('Nothing matched. Sorting by time on default.')
                        return self.stores_by_time_selection(store_info)
            else:
                LOG.info(f"found store {store_info}")
                self.speak_stores(store_info)
        return 3, None

    def execute(self, user_request, mall_link):
        count = 0
        LOG.info('Start execute')
        while count < 3 and user_request is not None and mall_link is not None:
            new_count, user_request = self.find_store(user_request, mall_link)
            count = count + new_count
        user_request = self.start_again()
        LOG.info(str(user_request))
        if user_request is not None:
            LOG.info('New execution')
            self.execute(user_request, mall_link)
        else:
            return None

    def _start_mall_parser_prompt(self, message):
        if self.neon_in_request(message):
            LOG.info('Prompting Mall parsing start')
            self.make_active()
            if message is not None:
                LOG.info('new message' + str(message))
                user_request, mall_link = self.user_request_handling(message)
                LOG.info(mall_link)
                if user_request is not None:
                    if self.execute(user_request, mall_link) is not None:
                        LOG.info('executed')
                        return
                    else:
                        self.speak_dialog('finished')
            else:
                self.speak_dialog('finished')
        else:
            return


def create_skill():
    return DirectorySkill()
