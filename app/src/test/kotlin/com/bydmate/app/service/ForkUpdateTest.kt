package com.bydmate.app.service

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.bydmate.app.util.AppStrings
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.Protocol
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [29])
class ForkUpdateTest {
    private val context: Context = ApplicationProvider.getApplicationContext()

    private fun checker(json: String, status: Int = 200): UpdateChecker {
        val client = OkHttpClient.Builder().addInterceptor { chain ->
            assertEquals("https://api.github.com/repos/Dmitrijsmok/BYDMate/releases/latest", chain.request().url.toString())
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                .code(status).message("test").body(json.toResponseBody("application/json".toMediaType())).build()
        }.build()
        return UpdateChecker(client, mockk<AppStrings>(relaxed = true))
    }

    @Test fun `only the exact fork asset is selected`() = runTest {
        val url = "https://github.com/Dmitrijsmok/BYDMate/releases/download/v99.0.0/DiLink3Friendly-v99.0.0.apk"
        val json = """{"tag_name":"v99.0.0","assets":[
            {"name":"BYDMate-v99.0.0.apk","browser_download_url":"https://github.com/AndyShaman/BYDMate/releases/download/v99.0.0/BYDMate-v99.0.0.apk"},
            {"name":"DiLink3Friendly-v99.0.0.apk","browser_download_url":"$url"}]}"""
        assertEquals(url, checker(json).checkForUpdate(context, true)?.downloadUrl)
    }

    @Test fun `upstream URL with a fork filename is rejected`() = runTest {
        val json = """{"tag_name":"v99.0.0","assets":[{"name":"DiLink3Friendly-v99.0.0.apk",
            "browser_download_url":"https://github.com/AndyShaman/BYDMate/releases/download/v99.0.0/DiLink3Friendly-v99.0.0.apk"}]}"""
        assertTrue(runCatching { checker(json).checkForUpdate(context, true) }.isFailure)
    }

    @Test fun `missing releases and older versions do not offer an update`() = runTest {
        assertNull(checker("{}", 404).checkForUpdate(context, true))
        assertNull(checker("""{"tag_name":"v0.0.1"}""").checkForUpdate(context, true))
    }
}
