import os
from wx.lib.agw.floatspin import FloatSpin
from PIL import Image, ImageDraw, ImageFont
import re
import wx
import pickle
from datetime import date, timedelta, datetime
from subprocess import Popen
import threading
from threading import Thread
import ctypes
import time

VERSION = '2025.01.31'
PYTHON = '3.10.10'
WXPYTHON = '4.2.0'
PYINSTALLER = '6.10.0'
TITLE = 'ConcatImgs'

MARGIN_TOP = 100
PAGE_SPACING = 10
LEFT_CROP = 30
RIGHT_CROP = 30
LIMIT_NUMBER_IMAGES = 5
DISPLAY_PAGE = True
DISPLAY_PAGE_FROM = 1
# START_PAGE_NUM = 1
DISPLAY_NEWS = True
NEWS_PAGE = 6
NEWS_COLOR = (255, 0, 0, 255)
DISPLAY_PUBDATE_SICI = True
SICI_VOL = '' # 2023-01-01(일) 기준
SICI_NO = '' # 2023-01-01(일) 기준
COVER_IMAGE = ''
OUTFILE_EXTENSION = 0 # '.jpg'

WILDCARD = f'이미지 파일 (*.png;*.jpg;*.jpeg;*.jpe;*.jfif)|*.png;*.jpg;*.jpeg;*.jpe;*.jfif|모든 파일 (*.*)|*.*'


class ResultEvent(wx.PyEvent):
    def __init__(self, data):
        wx.PyEvent.__init__(self)
        self.SetEventType(-1)
        self.data = data


class WorkerThread(Thread):
    def __init__(self, parent):
        Thread.__init__(self)
        self.parent = parent
        self.parent.task_done = False

    def run(self):
        self.parent.concatImgs()
        self.parent.task_done = True
        self.abort()

    def abort(self):
        if self.parent.task_done:
            wx.PostEvent(self.parent, ResultEvent(f'finished-{self.parent.task}'))
        else:
            wx.PostEvent(self.parent, ResultEvent(f'cancelled-{self.parent.task}'))

        self.raise_exception()

    def raise_exception(self):
        thread_id = self.get_id()
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id,
                                                         ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('예외 발생 실패')

    def get_id(self):
        if hasattr(self, '_thread_id'):
            return self._thread_id

        for t in threading.enumerate():
            if t is self:
                return t.native_id


class ConcatImgs(wx.Frame):
    def __init__(self, parent):
        self.name_list = {}
        self.files_added = []
        self.image_list = []
        self.full_width = 0
        self.full_height = 0
        self.page_size = []
        self.outfile_extensions = ['.jpg', '.png', '.webp', '.tiff', '.bmp']
        self.outfile = ''
        self.outfile_basename = ''
        self.index = 1
        self.task = ''
        self.key = ''
        self.progrdlg = None
        self.cancelled = False
        self.task_done = False
        self.worker = None
        self.page_spacing = PAGE_SPACING
        self.margin_top = MARGIN_TOP
        self.left_crop = LEFT_CROP
        self.right_crop = RIGHT_CROP
        self.limit_number_images = LIMIT_NUMBER_IMAGES
        self.display_page = DISPLAY_PAGE
        self.display_news = DISPLAY_NEWS
        self.display_page_from = DISPLAY_PAGE_FROM
        # self.start_page_num = START_PAGE_NUM
        self.news_page = NEWS_PAGE
        self.news_color = NEWS_COLOR
        self.display_pubdate_sici = DISPLAY_PUBDATE_SICI
        self.sici_vol = SICI_VOL
        self.sici_no = SICI_NO
        self.cover_image = COVER_IMAGE
        self.outfile_extension = OUTFILE_EXTENSION

        self.im = None
        self.config = {}
        self.rd = None

        try:
            with open('config.pickle', 'rb') as f:
                self.config = pickle.load(f)
                if 'margin_top' in self.config:
                    self.margin_top = self.config['margin_top']
                else:
                    self.config['margin_top'] = self.margin_top

                if 'page_spacing' in self.config:
                    self.page_spacing = self.config['page_spacing']
                else:
                    self.config['page_spacing'] = self.page_spacing

                if 'left_crop' in self.config:
                    self.left_crop = self.config['left_crop']
                else:
                    self.config['left_crop'] = self.left_crop

                if 'right_crop' in self.config:
                    self.right_crop = self.config['right_crop']
                else:
                    self.config['right_crop'] = self.right_crop

                if 'limit_number_images' in self.config:
                    self.limit_number_images = self.config['limit_number_images']
                else:
                    self.config['limit_number_images'] = self.limit_number_images

                if 'display_page' in self.config:
                    self.display_page = self.config['display_page']
                else:
                    self.config['display_page'] = self.display_page

                if 'display_page_from' in self.config:
                    self.display_page_from = self.config['display_page_from']
                else:
                    self.config['display_page_from'] = self.display_page_from

                """
                if 'start_page_num' in self.config:
                    self.start_page_num = self.config['start_page_num']
                else:
                    self.config['start_page_num'] = self.start_page_num
                """

                if 'display_news' in self.config:
                    self.display_news = self.config['display_news']
                else:
                    self.config['display_news'] = self.display_news

                if 'news_page' in self.config:
                    self.news_page = self.config['news_page']
                else:
                    self.config['news_page'] = self.news_page

                if 'news_color' in self.config:
                    self.news_color = self.config['news_color']
                else:
                    self.config['news_color'] = self.news_color

                if 'display_pubdate_sici' in self.config:
                    self.display_pubdate_sici = self.config['display_pubdate_sici']
                else:
                    self.config['display_pubdate_sici'] = self.display_pubdate_sici

                if 'sici_vol' in self.config:
                    self.sici_vol = self.config['sici_vol']
                else:
                    self.config['sici_vol'] = self.sici_vol

                if 'sici_no' in self.config:
                    self.sici_no = self.config['sici_no']
                else:
                    self.config['sici_no'] = self.sici_no

                if 'cover_image' in self.config:
                    self.cover_image = self.config['cover_image']
                else:
                    self.config['cover_image'] = self.cover_image

                if 'outfile_extension' in self.config:
                    self.outfile_extension = self.config['outfile_extension']
                else:
                    self.config['outfile_extension'] = self.outfile_extension


        except Exception as e:
            self.config['margin_top'] = MARGIN_TOP
            self.config['page_spacing'] = PAGE_SPACING
            self.config['left_crop'] = LEFT_CROP
            self.config['right_crop'] = RIGHT_CROP
            self.config['limit_number_images'] = LIMIT_NUMBER_IMAGES
            self.config['display_page'] = DISPLAY_PAGE
            self.config['display_news'] = DISPLAY_NEWS
            self.config['display_page_from'] = DISPLAY_PAGE_FROM
            # self.config['start_page_num'] = START_PAGE_NUM
            self.config['news_page'] = NEWS_PAGE
            self.config['news_color'] = NEWS_COLOR
            self.config['display_pubdate_sici'] = DISPLAY_PUBDATE_SICI
            self.config['sici_vol'] = SICI_VOL
            self.config['sici_no'] = SICI_NO
            self.config['cover_image'] = COVER_IMAGE
            self.config['outfile_extension'] = OUTFILE_EXTENSION

        wx.Frame.__init__(self, None, title=TITLE , size=(496, 195),
                          style = wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))

        # 메뉴
        self.menuBar = wx.MenuBar()
        self.menu1 = wx.Menu()
        self.menu1.Append(108, '설정...')
        self.menu1.AppendSeparator()
        self.menu1.Append(109, '닫기\tCtrl+W')
        self.menuBar.Append(self.menu1, '  파일  ')
        self.menu2 = wx.Menu()
        self.menu2.Append(204, TITLE)
        self.menuBar.Append(self.menu2, '  도움말  ')
        self.SetMenuBar(self.menuBar)

        # 컨트롤
        pn = wx.Panel(self)

        btnOpen = wx.Button(pn, -1, '작업 대상 지정', size=(300,40))
        btnOpen2 = wx.Button(pn, -1, '작업 대상 지정 2', size=(300,40))
        # btnSetup = wx.Button(pn, -1, '설정', size=(300,40))

        inner = wx.BoxSizer(wx.VERTICAL)
        inner.Add(btnOpen, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        inner.Add(btnOpen2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        # inner.Add(btnSetup, 0, wx.LEFT | wx.RIGHT, 10)

        self.sizer = sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(inner, 0, wx.TOP | wx.BOTTOM, 60)

        pn.SetSizer(sizer)
        sizer.SetSizeHints(self)
        self.Center()
        self.SetIcon(wx.Icon("data/concatimgs.ico"))

        # 이벤트
        # self.Bind(wx.EVT_MENU, self.OnOpenFile, id=101)
        # self.Bind(wx.EVT_MENU, self.OnOpenFile2, id=102)
        self.Bind(wx.EVT_MENU, self.OnSetup, id=108)
        self.Bind(wx.EVT_MENU, self.onclose, id=109)
        self.Bind(wx.EVT_MENU, self.onabout, id=204)
        self.Bind(wx.EVT_CLOSE, self.onwindowclose)
        btnOpen.Bind(wx.EVT_BUTTON, self.OnOpenFile)
        btnOpen2.Bind(wx.EVT_BUTTON, self.OnOpenFile2)
        # btnSetup.Bind(wx.EVT_BUTTON, self.OnSetup())
        self.Connect(-1, -1, -1, self.onresult)

    def OnSetup(self, evt=None):
        dlg = SetupDialog(self)
        val = dlg.ShowModal()
        dlg.Destroy()
        if val == wx.ID_OK:
            if dlg.changed[0]:
                self.margin_top = self.config['margin_top'] = int(dlg.fs.GetValue())

            if dlg.changed[1]:
                self.page_spacing = self.config['page_spacing'] = int(dlg.fs2.GetValue())

            if dlg.changed[2]:
                self.left_crop = self.config['left_crop'] = int(dlg.fs3.GetValue())

            if dlg.changed[3]:
                self.right_crop = self.config['right_crop'] = int(dlg.fs4.GetValue())

            if dlg.changed[4]:
                self.limit_number_images = self.config['limit_number_images'] = int(dlg.fs5.GetValue())

            if dlg.changed[5]:
                self.display_page = self.config['display_page'] = dlg.cbDisplayPage.GetValue()

            """
            if dlg.changed[6]:
                self.display_page_from = self.config['display_page_from'] = int(dlg.fs6.GetValue())

            if dlg.changed[7]:
                self.start_page_num = self.config['start_page_num'] = int(dlg.fs7.GetValue())
            """

            if dlg.changed[8]:
                self.display_news = self.config['display_news'] = dlg.cbDisplayNews.GetValue()

            if dlg.changed[9]:
                self.news_page = self.config['news_page'] = int(dlg.fs8.GetValue())

            if dlg.changed[10]:
                self.news_color = self.config['news_color'] = dlg.news_color

            if dlg.changed[11]:
                self.display_pubdate_sici = self.config['display_pubdate_sici'] = dlg.cbDisplayPubdateSici.GetValue()

            if dlg.changed[12]:
                self.sici_vol = self.config['sici_vol'] = dlg.txtSiciVol.GetValue()

            if dlg.changed[13]:
                self.sici_no = self.config['sici_no'] = dlg.txtSiciNo.GetValue()

            if dlg.changed[14]:
                self.cover_image = self.config['cover_image'] = dlg.cover_image

            if dlg.changed[15]:
                self.outfile_extension = self.config['outfile_extension'] = dlg.outfile_extension

            with open('config.pickle', 'wb') as f:
                pickle.dump(self.config, f)


    def OnOpenFile2(self, evt):
        fileDialog = wx.FileDialog(self, '파일을 지정하세요(복수 선택 가능).', wildcard=WILDCARD, style=wx.FD_MULTIPLE)
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return

        paths = fileDialog.GetPaths()
        fileDialog.Destroy()

        self.files_added = []
        for path in paths:
            self.files_added.append(path)

        self.files_added = sorted(self.files_added)

        self.rd = MyRearrangeDialog(self)
        if self.rd.ShowModal() == wx.ID_CANCEL:
            return

        self.files_added = [self.rd.lc.GetString(x) for x in range(len(self.rd.items)) if self.rd.lc.IsChecked(x)]
        self.rd.Destroy()

        self.doIt()

    def OnOpenFile(self, evt):
        fileDialog = wx.FileDialog(self, '파일을 지정하세요(작업대상 중 아무거나 1개).',
                                   wildcard=WILDCARD)
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return

        path = fileDialog.GetPath()
        fileDialog.Destroy()
        self.files_added = [path]

        key = ''
        directory, filename = os.path.split(self.files_added[0])
        name, ext = os.path.splitext(filename)

        r = re.search(r'(.+)\d+\.', filename)
        if r:
            key = r.group(1)

        r = re.search(r'.+(\d+)\.', filename)
        if r:
            serial = r.group(1)

        for i in range(1000):
            file = f'{directory}\\{key}{i}{ext}'
            if os.path.exists(file):
                if file not in self.files_added:
                    self.files_added.append(file)
            else:
                file = f'{directory}\\{key[:-1]}{i}{ext}'
                if os.path.exists(file):
                    if file not in self.files_added:
                        self.files_added.append(file)
                else:
                    file = f'{directory}\\{key[:-2]}{i}{ext}'
                    if os.path.exists(file):
                        if file not in self.files_added:
                            self.files_added.append(file)

            if len(self.files_added) >= self.limit_number_images:
                break

        for file in self.files_added:
            try:
                im = Image.open(file)
            except:
                self.files_added = []
                msg = f'이미지 파일이 맞는지 확인해주세요.\n\n{file}'
                wx.MessageBox(msg, TITLE, wx.ICON_EXCLAMATION | wx.OK)
                return

        self.files_added = sorted(self.files_added)

        self.rd = MyRearrangeDialog(self)
        if self.rd.ShowModal() == wx.ID_CANCEL:
            return

        self.files_added = [self.rd.lc.GetString(x) for x in range(len(self.rd.items)) if self.rd.lc.IsChecked(x)]
        self.rd.Destroy()

        self.doIt()

    def doIt(self):
        self.task = 'concat'
        message = '이미지 합치기 준비 중...'
        self.progrdlg = wx.GenericProgressDialog('이미지 합치기', message,
                        maximum=len(self.files_added)+1, parent=self,
                        style=0 | wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_CAN_ABORT)

        msg = f'작업할 이미지 개수: 최대 {self.limit_number_images}개'
        print(msg)

        self.key = ''
        self.directory, filename = os.path.split(self.files_added[0])
        r = re.search(r'(.*?)\d+\.', filename)
        if r:
            self.key = r.group(1)

        try:
            if not(os.path.isdir(f'{self.directory}\\output')):
                os.makedirs(f'{self.directory}\\output', exist_ok=True)
        except OSError as e:
            return

        self.full_width, self.full_height, self.index = 0, self.margin_top, 1
        self.image_list = []

        if self.cover_image:
            im = Image.open(self.files_added[0])
            width, height = im.size
            width_resize = width - (self.left_crop+self.right_crop)
            height_resize = height * (width_resize/width)
            size = (width_resize, int(height_resize))
            infile = self.cover_image
            extension = self.outfile_extensions[self.outfile_extension]
            outfile = os.path.splitext(infile)[0] + extension
            if infile != outfile:
                try:
                    im = Image.open(infile)
                    im.thumbnail(size, Image.Resampling.LANCZOS)
                    im.save(outfile)

                except IOError as e:
                    print(e)
                    return

            self.progrdlg.Update(0, outfile)
            file = outfile  # self.cover_image
            im = Image.open(file)
            print(f'"{file}"를 불러옴.')
            width, height = im.size

            if self.full_height + height > 65000:
                self.concatImgs()
                self.index = self.index + 1
                self.image_list = []
                self.full_width, self.full_height = 0, 0

            self.image_list.append(im)
            self.full_width = max(self.full_width, width)
            self.full_height += height + self.page_spacing

        count = 1
        for file in self.files_added:
            im = Image.open(file)
            print(f'"{file}"를 불러옴.')
            width, height = im.size

            if self.full_height + height > 65000:
                self.concatImgs()
                self.index = self.index + 1
                self.image_list = []
                self.full_width, self.full_height = 0, 0

            self.image_list.append(im)
            self.full_width = max(self.full_width, width)
            self.full_height += height + self.page_spacing
            count += 1
            if count > self.limit_number_images:
                break

        self.full_height -= self.page_spacing
        #self.concatImgs()
        self.worker = WorkerThread(self)
        self.worker.daemon = True
        self.worker.start()

    def checkproc_concat(self, i):
        if i >= len(self.files_added):
            return

        if self.progrdlg.WasCancelled():
            self.worker.abort()
            return

        msg = (f'{self.files_added[i]}')
        self.progrdlg.Update(i + 1, msg)

    def concatImgs(self):
        canvas = Image.new('RGB', (self.full_width-(self.left_crop+self.right_crop), self.full_height), '#999')
        output_height = 0
        page = 1
        self.page_size = []
        for im in self.image_list:
            width, height = im.size
            if page == 1:
                x, y = 0, (output_height + self.margin_top)
                output_height += (height + self.page_spacing + self.margin_top)
            else:
                x, y = self.left_crop*-1, output_height
                output_height += (height + self.page_spacing)

            canvas.paste(im, (x, y))
            self.page_size.append((output_height, (width-(self.left_crop+self.right_crop), height)))
            page += 1
            if page > self.limit_number_images + 1:
                break

        extension = self.outfile_extensions[self.outfile_extension]
        print(f'"{self.key}_합치기_{self.index}{extension}"로 이미지 합치기 시작.')

        self.outfile_basename = f'{self.key}_합치기_{self.index}'
        outfile = f'{self.directory}\output\{self.outfile_basename}{extension}'
        canvas.save(outfile)

        with Image.open(outfile) as im:
            draw = ImageDraw.Draw(im)
            draw.rectangle((0, 0, self.full_width, self.margin_top), fill='#fff')

            # font = ImageFont.load_default()
            font = ImageFont.truetype('malgun.ttf', 20)
            font2 = ImageFont.truetype('malgunbd.ttf', 20)
            I1 = ImageDraw.Draw(im)
            num_pages = len(self.page_size)
            for i in range(num_pages):
                self.checkproc_concat(i)
                page = i + 1
                if page == 1:
                    if self.display_pubdate_sici:
                        font3 = ImageFont.truetype('malgunbd.ttf', 17)
                        x = self.page_size[i][1][0] - 220
                        y = self.page_size[i][0] - self.page_size[i][1][1] + 20
                        today = date.today()
                        sunday = today + timedelta( (6-today.weekday()) % 7 )
                        publication_date = sunday.strftime('%Y{0} %m{1} %d{2}').format(*'년월일')
                        year_sunday = sunday.year
                        date_base = datetime.strptime('2023-01-01', '%Y-%m-%d').date()
                        year_base = date_base.year
                        years_diff = year_sunday - year_base
                        days_diff = (sunday - date_base).days
                        sici_vol = int(self.sici_vol) + years_diff
                        sici_no = int(self.sici_no) + (days_diff//7)
                        text = f'{publication_date} | 제{sici_vol}권 {sici_no}호'
                        I1.text((x, y), text, font=font3, fill='#000')
                else:
                    x = self.page_size[i][1][0] - 55
                    y = self.page_size[i][0] - self.page_size[i][1][1] + 10
                    if self.display_page:
                        text = f'{page}'
                        left, top, right, bottom = I1.textbbox((x, y), text, font=font)
                        I1.rectangle((left-5, top-5, right+5, bottom+5), fill='#333')
                        I1.text((x, y), text, font=font, fill='#fff')

                    if self.display_news:
                        if page == self.news_page:
                            text2= '▣ 교회소식'
                            x2 = 25
                            left, top, right, bottom = I1.textbbox((x2, y), text2, font=font2)
                            I1.rectangle((left-5, top-5, right+5, bottom+5), fill=self.news_color)
                            I1.text((x2, y), text2, font=font2, fill='#fff')
            im.save(outfile)

        self.im = im

    def onresult(self, evt):
        # self.SetFocus()  # VideoCut 프레임 활성화된 상태 유지
        if evt.data == 'finished-concat':
            self.progrdlg.Destroy()
            self.worker = None
            print('이미지 합치기 완료.')
            extension = self.outfile_extensions[self.outfile_extension]
            msg = f'이미지 합치기 완료.\n\n저장 폴더: {self.directory}\\output\n\n파일명: {self.outfile_basename}{extension}'
            wx.MessageBox(msg, TITLE, wx.ICON_INFORMATION | wx.OK)
            Popen(f'explorer /select, "{self.directory}\\output\\{self.outfile_basename}{extension}"')
            # self.im.show()

    def onabout(self, evt):
        message = f'{TITLE}\n버전 {VERSION}\n \n' \
                  f'Python {PYTHON}\nwxPython {WXPYTHON}\nPyInstaller {PYINSTALLER}\n \nHS Kang'
        wx.MessageBox(message, TITLE, wx.ICON_INFORMATION | wx.OK)

    def onclose(self, evt):
        self.Close()

    def onwindowclose(self, evt):
        self.Destroy()


class SetupDialog(wx.Dialog):
    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title = '설정', size=(358, 495))
        self.parent = parent
        self.changed = [False] * 16
        self.news_color = parent.news_color
        self.sici_vol = parent.sici_vol
        self.sici_no = parent.sici_no
        self.cover_image = parent.cover_image
        self.outfile_extension = parent.outfile_extension

        st = wx.StaticText(self, -1, "맨 위 여백")
        self.fs = FloatSpin(self, -1, value=parent.margin_top, min_val=0, max_val=999, increment=1,
                            digits=0, size=(52, -1))
        st_2 = wx.StaticText(self, -1, " px")

        st2 = wx.StaticText(self, -1, "쪽 간격")
        self.fs2 = FloatSpin(self, -1, value=parent.page_spacing, min_val=0, max_val=999, increment=1,
                             digits=0, size=(52, -1))
        st2_2 = wx.StaticText(self, -1, " px")

        st3 = wx.StaticText(self, -1, "왼쪽 잘라버리기")
        self.fs3 = FloatSpin(self, -1, value=parent.left_crop, min_val=0, max_val=999, increment=1,
                             digits=0, size=(52, -1))
        st3_2 = wx.StaticText(self, -1, " px")

        st4 = wx.StaticText(self, -1, "오른쪽 잘라버리기")
        self.fs4 = FloatSpin(self, -1, value=parent.right_crop, min_val=0, max_val=999, increment=1,
                             digits=0, size=(52, -1))
        st4_2 = wx.StaticText(self, -1, " px")

        st5 = wx.StaticText(self, -1, "작업 대상 이미지(표지 제외) 최대")
        self.fs5 = FloatSpin(self, -1, value=parent.limit_number_images, min_val=1, max_val=99, increment=1,
                             digits=0, size=(45, -1))
        st5_2 = wx.StaticText(self, -1, "개")

        self.cbDisplayPage = wx.CheckBox(self, -1, "쪽 표시(표지에는 표시하지 않음)", size=(-1, 22))
        self.cbDisplayPage.SetValue(parent.display_page)

        """
        self.st6 = wx.StaticText(self, -1, "째 이미지부터")
        self.fs6 = FloatSpin(self, -1, value=parent.display_page_from, min_val=1, max_val=int(self.fs5.GetValue()), increment=1,
                             digits=0, size=(45, -1))
        self.st6.Enable(parent.display_page)
        self.fs6.Enable(parent.display_page)
        """
        """
        self.st7 = wx.StaticText(self, -1, "시작 번호")
        self.fs7 = FloatSpin(self, -1, value=parent.start_page_num, min_val=1, max_val=int(self.fs5.GetValue()), increment=1,
                             digits=0, size=(52, -1))
        self.st7_2 = wx.StaticText(self, -1, "")
        self.st7.Enable(self.cbDisplayPage.GetValue())
        self.fs7.Enable(self.cbDisplayPage.GetValue())
        """

        self.cbDisplayNews = wx.CheckBox(self, -1, "'교회소식' 라벨 표시", size=(-1, 22))
        self.cbDisplayNews.SetValue(parent.display_news)

        self.st8 = wx.StaticText(self, -1, "쪽(표지 포함)에")
        self.fs8 = FloatSpin(self, -1, value=parent.news_page, min_val=1, max_val=int(self.fs5.GetValue())+1, increment=1,
                             digits=0, size=(45, -1))
        self.btnColor = wx.Button(self, -1, '색상 지정')
        self.st8_2 = wx.StaticText(self, -1, "■")
        self.st8_2.SetForegroundColour(self.news_color)

        self.st8.Enable(parent.display_news)
        self.fs8.Enable(parent.display_news)
        self.btnColor.Enable(parent.display_news)

        self.cbDisplayPubdateSici = wx.CheckBox(self, -1, "발행일자·권호 표시", size=(-1, 22))
        self.cbDisplayPubdateSici.SetValue(parent.display_pubdate_sici)

        self.st9 = wx.StaticText(self, -1, "권호(2023.1.1.자): ")
        self.txtSiciVol = wx.TextCtrl(self, -1, parent.sici_vol, size=(30, -1))
        self.st10 = wx.StaticText(self, -1, "권")
        self.txtSiciNo = wx.TextCtrl(self, -1, parent.sici_no, size=(30, -1))
        self.st11 = wx.StaticText(self, -1, "호")

        self.btnCoverImage = wx.Button(self, -1, '표지 이미지 지정')
        self.cover_image = os.path.split(parent.cover_image)[1]
        self.st12 = wx.StaticText(self, -1, self.cover_image)
        if not self.st12.GetLabel():
            self.st12.SetLabel('미지정')

        self.st13 = wx.StaticText(self, -1, "출력파일 확장자")
        self.cbExtension = wx.ComboBox(self, -1, size=(65, -1), choices=parent.outfile_extensions)
        self.cbExtension.Select(parent.config['outfile_extension'])

        inner = wx.BoxSizer(wx.HORIZONTAL)
        inner.Add((20, -1), 0)
        inner.Add(st, 0, wx.TOP, 5)
        inner.Add(self.fs, 0, wx.LEFT | wx.BOTTOM, 5)
        inner.Add(st_2, 0, wx.TOP, 5)
        inner.Add((10, -1), 0)

        inner2 = wx.BoxSizer(wx.HORIZONTAL)        
        inner2.Add((20, -1), 0)
        inner2.Add(st2, 0, wx.TOP, 5)
        inner2.Add(self.fs2, 0, wx.LEFT | wx.BOTTOM, 5)
        inner2.Add(st2_2, 0, wx.TOP, 5)
        inner2.Add((10, -1), 0)

        inner3 = wx.BoxSizer(wx.HORIZONTAL)
        inner3.Add((20, -1), 0)
        inner3.Add(st3, 0, wx.TOP, 5)
        inner3.Add(self.fs3, 0, wx.LEFT | wx.BOTTOM, 5)
        inner3.Add(st3_2, 0, wx.TOP, 5)
        inner3.Add((10, -1), 0)

        inner4 = wx.BoxSizer(wx.HORIZONTAL)
        inner4.Add((20, -1), 0)
        inner4.Add(st4, 0, wx.TOP, 5)
        inner4.Add(self.fs4, 0, wx.LEFT | wx.BOTTOM, 5)
        inner4.Add(st4_2, 0, wx.TOP, 5)
        inner4.Add((10, -1), 0)

        inner5 = wx.BoxSizer(wx.HORIZONTAL)
        inner5.Add((20, -1), 0)
        inner5.Add(st5, 0, wx.TOP, 5)
        inner5.Add(self.fs5, 0, wx.LEFT | wx.BOTTOM, 5)
        inner5.Add(st5_2, 0, wx.TOP, 5)
        inner5.Add((10, -1), 0)

        inner6 = wx.BoxSizer(wx.HORIZONTAL)
        inner6.Add((20, -1), 0)
        inner6.Add(self.cbDisplayPage, 0, wx.LEFT | wx.BOTTOM, 5)
        """
        inner6.Add((20, -1), 0)
        inner6.Add(self.fs6, 0, wx.LEFT | wx.BOTTOM, 5)
        inner6.Add(self.st6, 0, wx.TOP, 5)
        """
        inner6.Add((10, -1), 0)

        """
        inner7 = wx.BoxSizer(wx.HORIZONTAL)
        inner7.Add((41, -1), 0)
        inner7.Add(self.st7, 0, wx.TOP, 5)
        inner7.Add(self.fs7, 0, wx.LEFT | wx.BOTTOM, 5)
        inner7.Add(self.st7_2, 0, wx.TOP, 5)
        inner7.Add((10, -1), 0)
        """

        inner8 = wx.BoxSizer(wx.HORIZONTAL)
        inner8.Add((20, -1), 0)
        inner8.Add(self.cbDisplayNews, 0, wx.LEFT | wx.BOTTOM, 5)
        inner8.Add((20, -1), 0)
        inner8.Add(self.fs8, 0, wx.LEFT | wx.BOTTOM, 5)
        inner8.Add(self.st8, 0, wx.TOP, 5)
        inner8.Add((10, -1), 0)

        inner9 = wx.BoxSizer(wx.HORIZONTAL)
        inner9.Add((41, -1), 0)
        inner9.Add(self.btnColor, 0, wx.BOTTOM, 5)
        inner9.Add((5, -1), 0)
        inner9.Add(self.st8_2, 0, wx.TOP, 3)
        inner9.Add((10, -1), 0)

        inner10 = wx.BoxSizer(wx.HORIZONTAL)
        inner10.Add((20, -1), 0)
        inner10.Add(self.cbDisplayPubdateSici, 0, wx.LEFT | wx.BOTTOM, 5)
        inner10.Add((10, -1), 0)

        inner11 = wx.BoxSizer(wx.HORIZONTAL)
        inner11.Add((41, -1), 0)
        inner11.Add(self.st9, 0, wx.TOP, 3)
        inner11.Add(self.txtSiciVol, 0, wx.LEFT | wx.BOTTOM, 5)
        inner11.Add(self.st10, 0, wx.TOP, 3)
        inner11.Add((5, -1), 0)
        inner11.Add(self.txtSiciNo, 0, wx.LEFT | wx.BOTTOM, 5)
        inner11.Add(self.st11, 0, wx.TOP, 3)
        inner11.Add((10, -1), 0)

        inner12 = wx.BoxSizer(wx.HORIZONTAL)
        inner12.Add((20, -1), 0)
        inner12.Add(self.btnCoverImage, 0, wx.BOTTOM, 5)
        inner12.Add((10, -1), 0)
        inner12.Add(self.st12, 0, wx.TOP | wx.BOTTOM, 5)
        inner12.Add((10, -1), 0)

        inner13 = wx.BoxSizer(wx.HORIZONTAL)
        inner13.Add((20, -1), 0)
        inner13.Add(self.st13, 0, wx.TOP | wx.BOTTOM, 5)
        inner13.Add((10, -1), 0)
        inner13.Add(self.cbExtension, 0, wx.BOTTOM, 5)
        inner13.Add((10, -1), 0)

        btnsizer = wx.StdDialogButtonSizer()
        self.btnOk = btnOk = wx.Button(self, wx.ID_OK, '적용', size=(-1, 25))
        btnOk.Enable(False)
        self.btnCancel = btnCancel = wx.Button(self, wx.ID_CANCEL, '취소', size=(-1, 25))
        btnCancel.SetFocus()
        btnsizer.Add((90, -1), 0)
        btnsizer.AddButton(btnOk)
        btnsizer.AddButton(btnCancel)
        btnsizer.Realize()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(inner, 0, wx.TOP, 20)
        sizer.Add(inner2, 0, wx.TOP, 5)
        sizer.Add(inner3, 0, wx.TOP, 5)
        sizer.Add(inner4, 0, wx.TOP, 5)
        sizer.Add(inner5, 0, wx.TOP, 5)
        sizer.Add(inner6, 0, wx.TOP, 5)
        # sizer.Add(inner7, 0, wx.TOP, 0)
        sizer.Add(inner8, 0, wx.TOP, 5)
        sizer.Add(inner9, 0, wx.TOP, 0)
        sizer.Add(inner10, 0, wx.TOP, 5)
        sizer.Add(inner11, 0, wx.TOP, 0)
        sizer.Add(inner12, 0, wx.TOP, 5)
        sizer.Add(inner13, 0, wx.TOP, 5)
        sizer.Add(btnsizer, 0, wx.TOP, 20)
        self.SetSizer(sizer)
        self.Center()

        self.fs.Bind(wx.lib.agw.floatspin.EVT_FLOATSPIN, self.onevtfloatspin)
        self.fs2.Bind(wx.lib.agw.floatspin.EVT_FLOATSPIN, self.onevtfloatspin2)
        self.fs3.Bind(wx.lib.agw.floatspin.EVT_FLOATSPIN, self.onevtfloatspin3)
        self.fs4.Bind(wx.lib.agw.floatspin.EVT_FLOATSPIN, self.onevtfloatspin4)
        self.fs5.Bind(wx.lib.agw.floatspin.EVT_FLOATSPIN, self.onevtfloatspin5)
        self.cbDisplayPage.Bind(wx.EVT_CHECKBOX, self.checkDisplayPage)
        # self.fs6.Bind(wx.lib.agw.floatspin.EVT_FLOATSPIN, self.onevtfloatspin6)
        # self.fs7.Bind(wx.lib.agw.floatspin.EVT_FLOATSPIN, self.onevtfloatspin7)
        self.cbDisplayNews.Bind(wx.EVT_CHECKBOX, self.checkDisplayNews)
        self.fs8.Bind(wx.lib.agw.floatspin.EVT_FLOATSPIN, self.onevtfloatspin8)
        self.btnColor.Bind(wx.EVT_BUTTON, self.onevtbuttoncolor)
        self.cbDisplayPubdateSici.Bind(wx.EVT_CHECKBOX, self.checkDisplayPubdateSici)
        self.txtSiciVol.Bind(wx.EVT_TEXT, self.oneventsicivol)
        self.txtSiciNo.Bind(wx.EVT_TEXT, self.oneventsicino)
        # self.Bind(wx.EVT_RADIOBUTTON, self.onradiogroup)
        self.btnCoverImage.Bind(wx.EVT_BUTTON, self.onevtbuttoncoverimage)
        self.cbExtension.Bind(wx.EVT_COMBOBOX, self.oncbextension)

        self.CenterOnScreen()

    def onevtfloatspin(self, evt):
        self.changed[0] = (self.fs.GetValue() !=self.parent.margin_top)
        self.setcontrols()

    def onevtfloatspin2(self, evt):
        self.changed[1] = (self.fs2.GetValue() !=self.parent.page_spacing)
        self.setcontrols()

    def onevtfloatspin3(self, evt):
        self.changed[2] = (self.fs3.GetValue() !=self.parent.left_crop)
        self.setcontrols()

    def onevtfloatspin4(self, evt):
        self.changed[3] = (self.fs4.GetValue() !=self.parent.right_crop)
        self.setcontrols()

    def onevtfloatspin5(self, evt):
        val = self.fs5.GetValue()
        self.changed[4] = (val !=self.parent.limit_number_images)
        self.fs8.SetRange(1, val + 1)
        """
        if self.fs6.GetValue() > val:
            self.fs6.SetValue(val)
        """
        if self.fs8.GetValue() > val + 1:
            self.fs8.SetValue(val + 1)

        self.setcontrols()

    def checkDisplayPage(self, evt):
        display_page = self.cbDisplayPage.GetValue()
        self.changed[5] = (display_page !=self.parent.display_page)
        """
        self.st6.Enable(display_page)
        self.fs6.Enable(display_page)
        self.st7.Enable(display_page)
        self.fs7.Enable(display_page)
        self.st7_2.Enable(display_page)
        """
        self.setcontrols()

    """
    def onevtfloatspin6(self, evt):
        self.changed[6] = (self.fs6.GetValue() !=self.parent.display_page_from)
        self.setcontrols()

    def onevtfloatspin7(self, evt):
        self.changed[7] = (self.fs7.GetValue() !=self.parent.start_page_num)
        self.setcontrols()
    """

    def checkDisplayNews(self, evt):
        display_news = self.cbDisplayNews.GetValue()
        self.changed[8] = (display_news !=self.parent.display_news)
        self.st8.Enable(display_news)
        self.fs8.Enable(display_news)
        self.btnColor.Enable(display_news)
        self.setcontrols()

    def onevtfloatspin8(self, evt):
        self.changed[9] = (self.fs8.GetValue() !=self.parent.news_page)
        self.setcontrols()

    def onevtbuttoncolor(self, evt):
        data = wx.ColourData()
        data.SetColour(self.news_color)
        self.st8_2.SetLabel('')
        dlg = wx.ColourDialog(self, data)
        dlg.GetColourData().SetChooseFull(True)
        if dlg.ShowModal() == wx.ID_OK:
            data = dlg.GetColourData()
            self.news_color = data.GetColour().Get()
            self.changed[10] = (self.news_color != self.parent.news_color)
            self.st8_2.SetForegroundColour(self.news_color)
            self.setcontrols()

        self.st8_2.SetLabel('■')
        dlg.Destroy()

    def checkDisplayPubdateSici(self, evt):
        display_pubdate_sici = self.cbDisplayPubdateSici.GetValue()
        self.changed[11] = (display_pubdate_sici !=self.parent.display_pubdate_sici)
        self.st9.Enable(display_pubdate_sici)
        self.txtSiciNo.Enable(display_pubdate_sici)
        self.st10.Enable(display_pubdate_sici)
        self.txtSiciVol.Enable(display_pubdate_sici)
        self.txtSiciNo.Enable(display_pubdate_sici)
        self.st11.Enable(display_pubdate_sici)
        self.setcontrols()

    def oneventsicivol(self, evt):
        sici_vol = self.txtSiciVol.GetValue()
        self.changed[12] = (sici_vol !=self.parent.sici_vol)
        self.setcontrols()

    def oneventsicino(self, evt):
        sici_no = self.txtSiciNo.GetValue()
        self.changed[13] = (sici_no !=self.parent.sici_no)
        self.setcontrols()

    def onevtbuttoncoverimage(self, evt):
        default_dir, default_file = os.path.split(self.cover_image)
        dlg = wx.FileDialog(self, '파일을 지정하세요.', defaultDir=default_dir, defaultFile=default_file,
                            wildcard=WILDCARD)
        if dlg.ShowModal() == wx.ID_OK:
            self.cover_image = dlg.GetPath()
            self.changed[14] = (self.cover_image != self.parent.cover_image)
            cover_image = os.path.split(self.cover_image)[1]
            self.st12.SetLabel(cover_image)
            self.setcontrols()

        dlg.Destroy()

    def oncbextension(self, evt):
        sel = self.cbExtension.GetSelection()
        self.outfile_extension = sel
        self.changed[15] = (sel != self.parent.config['outfile_extension'])
        self.setcontrols()

    def setcontrols(self):
        if sum(self.changed) > 0:
            self.btnOk.Enable()
            # self.btnOk.SetFocus()
        else:
            self.btnOk.Disable()
            # self.btnCancel.SetFocus()

    def onwindowclose(self, evt=None):
        self.Destroy()


class MyRearrangeDialog(wx.RearrangeDialog):
    def __init__(self, parent):
        message = "☞ 파일 순서를 바꾸려면 해당 파일을 클릭한 후 Up / Down 버튼을 사용하여 조정하세요.\n" \
                  "☞ 작업 대상에서 제외하려면 선택을 해제하세요."

        order = []
        for num in range(0, len(parent.files_added)):
            order.append(num)

        items = parent.files_added[:]
        wx.RearrangeDialog.__init__(self, parent, message, TITLE, order, items)
        spacer = 10

        self.parent = parent

        self.btnOk = None
        for child in self.Children:
            if child.GetLabel() == 'OK':
                self.btnOk = child

            if child.GetLabel() == 'Cancel':
                child.SetLabel('취소')

        self.btnOk.SetLabel('확인')
        self.items = items
        # self.checked_items = []
        pn = wx.Panel(self)
        self.lc = self.GetList()
        self.lc.SetMinSize((500, 150))

        self.tc = wx.TextCtrl(pn, -1, f"{len(items)}", size=(40, -1), style=wx.TE_READONLY)
        self.btnAdd = wx.Button(pn, -1, '파일 추가')
        self.btnSetup = wx.Button(pn, -1, '설정')

        self.stPrecaution = wx.StaticText(pn, -1, "")
        self.stPrecaution.SetForegroundColour((255,0,0))
        self.stInformation = wx.StaticText(pn, -1, "")
        self.stInformation.SetForegroundColour((0,0,255))

        inner = wx.BoxSizer(wx.HORIZONTAL)
        inner.Add(wx.StaticText(pn, wx.ID_ANY, "선택 파일 수: "), 0, wx.TOP, 8)
        inner.Add(self.tc, 0, wx.TOP, 5)
        inner.Add((spacer, -1))
        inner.Add(self.btnAdd, 0, wx.TOP, 5)
        inner.Add((spacer, -1))
        inner.Add(self.btnSetup, 0, wx.TOP, 5)

        self.inner2 = inner2 = wx.BoxSizer(wx.VERTICAL)
        inner2.Add(self.stPrecaution, 0, wx.TOP, 0)
        inner2.Add(self.stInformation, 0, wx.TOP, 0)

        self.sizer = sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(inner, 0, wx.TOP, 0)
        sizer.Add(inner2, 0, wx.TOP, 5)

        pn.SetSizer(sizer)
        self.AddExtraControls(pn)
        self.Center()

        self.lc.Bind(wx.EVT_CHECKLISTBOX, self.OnCheck)
        self.lc.Bind(wx.EVT_LISTBOX, self.OnListBox)
        self.lc.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)
        self.btnAdd.Bind(wx.EVT_BUTTON, self.onadd)
        self.btnSetup.Bind(wx.EVT_BUTTON, self.OnSetup)
        self.btnOk.Bind(wx.EVT_BUTTON, self.OnOk)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        wx.CallAfter(self.OnCheck)

    def OnSetup(self, evt=None):
        self.parent.OnSetup()
        if int(self.tc.GetValue()) > self.parent.limit_number_images:
            s = f'☞ 선택된 파일 중 앞 {self.parent.limit_number_images}개를 제외한 나머지 파일은 ' \
                f'작업 대상에서 제외됩니다(설정값: 최대 {self.parent.limit_number_images}개).'
            s2 = f'☞ 선택된 파일 전부를 합치기 대상에 포함하려면 설정값을 변경해주세요.'
        else:
            s = s2 = ''

        self.stPrecaution.SetLabel(s)
        self.stInformation.SetLabel(s2)

    def OnSize(self, event=None):
        pass

    def OnOk(self, event):
        if not self.parent.sici_vol or not self.parent.sici_no:
            msg = '주보 권호를 입력하세요.\n\n '
            wx.MessageBox(msg, TITLE, wx.ICON_EXCLAMATION | wx.OK)
            self.OnSetup()
            return

        if not self.parent.cover_image:
            msg = '표지 이미지를 지정해주세요.\n\n '
            wx.MessageBox(msg, TITLE, wx.ICON_EXCLAMATION | wx.OK)
            self.OnSetup()

        event.Skip()

    def OnCheck(self, event=None):
        num_checked = len(self.lc.GetCheckedItems())
        self.tc.SetValue(f"{num_checked}")
        if num_checked > self.parent.limit_number_images:
            s = f'☞ 선택된 파일 중 앞 {self.parent.limit_number_images}개를 제외한 나머지 파일은 ' \
                f'작업 대상에서 제외됩니다(설정값: 최대 {self.parent.limit_number_images}개).'
            s2 = f'☞ 선택된 파일 전부를 합치기 대상에 포함하려면 설정값을 변경해주세요.'
        else:
            s = s2 = ''

        self.stPrecaution.SetLabel(s)
        self.stInformation.SetLabel(s2)

    def OnListBox(self, event):
        # print(f'You Selected {self.lc.GetString(event.GetSelection())}')
        pass

    def OnUnCheckOrCheckAll(self, event):
        doWhat = str(event.GetId()).endswith('1')
        #print('doWhat', doWhat)
        for i in range(0, len(self.items)):
            if doWhat:
                self.lc.Check(i, True)
            else:
                self.lc.Check(i, False)

        wx.CallAfter(self.OnCheck)

    def OnContextMenu(self, event):
        if len(self.lc.GetItems()) == 0:
            return

        menu = wx.Menu()
        ID_UNCHECKALL = 1000
        ID_CHECKALL = 1001
        mi1 = wx.MenuItem(menu, ID_UNCHECKALL, '전부 해제')
        mi2 = wx.MenuItem(menu, ID_CHECKALL, '전부 선택')
        menu.Append(mi1)
        menu.Append(mi2)
        menu.Bind(wx.EVT_MENU, self.OnUnCheckOrCheckAll, id=ID_UNCHECKALL)
        menu.Bind(wx.EVT_MENU, self.OnUnCheckOrCheckAll, id=ID_CHECKALL)
        self.PopupMenu(menu)
        menu.Destroy()

    def onadd(self, event):
        fileDialog = wx.FileDialog(self, '[이미지 합치기] 파일을 선택하세요(복수 선택).', wildcard=WILDCARD,
                                   style=wx.FD_MULTIPLE)
        if fileDialog.ShowModal() == wx.ID_CANCEL:
            return

        paths = fileDialog.GetPaths()
        fileDialog.Destroy()

        for path in paths:
            try:
                im = Image.open(path)
            except:
                msg = f'이미지 파일이 맞는지 확인해주세요.\n\n{path}'
                wx.MessageBox(msg, TITLE, wx.ICON_EXCLAMATION | wx.OK)
                return

        files_added = []
        for path in paths:
            self.items.append(path)
            self.lc.Append(path)
            self.lc.Check(len(self.items) - 1)
            files_added.append(path)

        if files_added:
            self.OnCheck()


# -------------------------------------------------------------------------------------------------------------------
if __name__ == '__main__':
    app = wx.App()
    frame = ConcatImgs(None)
    frame.Show()
    app.MainLoop()
