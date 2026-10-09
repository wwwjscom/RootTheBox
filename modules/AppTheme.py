# -*- coding: utf-8 -*-
"""
Created on Mar 14, 2012

@author: moloch

    Copyright 2012 Root the Box

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

from tornado.options import options
from tornado.web import UIModule

from models.Theme import Theme


class AppTheme(UIModule):
    def render(self, *args, **kwargs):
        """Includes different CSS themes based on user prefs"""
        theme = None
        session = self.handler.session
        if options.allow_user_to_change_theme and session is not None:
            # Resolve from the DB by id: a session's stored file list can name
            # a theme that has since been removed.
            theme = Theme.by_id(session.get("theme_id"))
        if theme is None:
            theme = Theme.default()
        return self.render_string("theme/theme.html", theme_files=theme)
